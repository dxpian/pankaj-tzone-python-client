from threading import Thread
from multiprocessing import Event
import json
import logging
import socket
import time
from pathlib import Path

socket.setdefaulttimeout(3)

def changeProbTemperature(buf: bytearray, temp: float, abnormal = False): 
    if abs(temp) > 1638.3:
        print("Failed to change temperature buffer. Temperature out of range")
        return buf

    if(len(buf) <= 65): 
        print(" Failed to change temperature buffer. Too short buffer length")
        return buf
    sign = 1 if temp < 0 else 0
    temp_raw = int(round(abs(temp) * 10))  # scale by 0.1

    value = (
        (1 << 15 if abnormal else 0) |
        (sign << 14) |
        (temp_raw & 0x3FFF)
    )

    # Convert to 2 bytes (big-endian — adjust if needed)
    buf[62:64] = value.to_bytes(2, byteorder="big", signed=False)

    return buf


class TcpClient(Thread): 
    def __init__(self, cfg, stop_flag:Event): 
        super().__init__()
        self.cfg = cfg
        self.flag = stop_flag
        self.server = cfg.server
        self.port = int(self.cfg.port)
        self.data = bytearray.fromhex(self.cfg.data)
        self.data_resp = bytearray.fromhex(self.cfg.data_resp)
        self.input_json = Path("Log/raw.json")
        self.retry_delay_sec = 1
        self.send_interval_sec = 0.01

        logging.info(f'socket client connect to server: [{self.server}]({self.port})')

    def _load_raw_datas(self):
        if not self.input_json.exists():
            raise FileNotFoundError(f"cannot find input json file: {self.input_json}")

        with self.input_json.open("r", encoding="utf-8") as f:
            payloads = json.load(f)

        if not isinstance(payloads, list):
            raise ValueError("input json must be a list of objects")

        raw_datas = []
        for item in payloads:
            if not isinstance(item, dict):
                continue
            raw = item.get("rawdata")
            rtc_time = item.get("rtctime")
            if isinstance(raw, str) and raw:
                raw_datas.append({"rawdata": raw, "rtctime": rtc_time})

        return raw_datas

    def _connect(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        s.settimeout(4)
        s.connect((self.server, self.port))
        logging.info("connected")
        data = s.recv(128)
        logging.debug(f"success to receive RTC time calibration from server:{data}")
        return s

    def run(self): 
        logging.debug("starting tcp client")
        try:
            datas = self._load_raw_datas()
        except Exception as err:
            logging.error(f"failed to load raw data json: {err}")
            return

        if not datas:
            logging.warning(f"no valid rawdata records in {self.input_json}")
            return

        index = 0
        s = None
        while index < len(datas):
            if self.flag.is_set():
                logging.info("stop flag set, stopping fill client")
                break

            try:
                if s is None:
                    s = self._connect()

                entry = datas[index]
                raw_data = entry.get("rawdata")
                rtc_time = entry.get("rtctime")
                logging.debug(f"processing the {index} paket")
                try:
                    byte_data = bytearray.fromhex(raw_data)
                except ValueError:
                    logging.warning(f"skip invalid rawdata hex at index {index}")
                    index += 1
                    continue

                logging.info(f"sending index={index}, rtctime={rtc_time}")
                # print(f"send byte data: {byte_data.hex()}")
                s.sendall(byte_data)
                data = s.recv(1024)
                logging.debug("client received: {}".format(data))
                index += 1
                time.sleep(self.send_interval_sec)

            except KeyboardInterrupt:
                logging.info("keyboard interrupted")
                break
            except socket.timeout:
                logging.warning(
                    f"socket client timeout at index {index}, reconnect and continue"
                )
                try:
                    if s is not None:
                        s.close()
                except Exception:
                    pass
                s = None
                time.sleep(self.retry_delay_sec)
            except Exception as err:
                logging.warning(
                    f"socket error at index {index}: {str(err)}; reconnect and continue"
                )
                try:
                    if s is not None:
                        s.close()
                except Exception:
                    pass
                s = None
                time.sleep(self.retry_delay_sec)

        try:
            if s is not None:
                s.close()
        except Exception:
            pass


