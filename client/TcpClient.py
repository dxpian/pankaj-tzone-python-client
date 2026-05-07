from threading import Thread
from multiprocessing import Event
import os
import json
import logging
import socket
import time
from datetime import datetime, timedelta
from signal import signal, SIG_DFL, SIG_IGN

socket.setdefaulttimeout(3)

def changeDateTime(buf: bytearray, dt: datetime) -> bytearray:
    """
    Replace bytes 20~25 in buf with encoded datetime.
    Format: [year-2000, month, day, hour, minute, second]
    """
    # encode datetime
    encoded = bytearray([
        dt.year - 2000,
        dt.month,
        dt.day,
        dt.hour,
        dt.minute,
        dt.second
    ])

    # replace in buffer
    buf[20:26] = encoded
    return buf

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
        self.data_resp = bytearray.fromhex(self.cfg.data_resp); 

        logging.info(f'socket client connect to server: [{self.server}]({self.port})')

    def run(self): 
        logging.debug("starting tcp client")
        
        # 190124110002433
        datas = [ "545a00462424040d0206000001901241100024331a050600000a0000001401d2044000203034020a1a5c0022000ea66d08550010aa000d3f005c002a031a003100000000000017170ec20d0a"]
        changeTime = True   # true if replace the timestamp into currrent timestamp
        cnt = 0
        while True: 
            try: 
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
                s.settimeout(4)
                s.connect((self.server, self.port))
                # receive time calibration data
                logging.info("connected")
                data = s.recv(128)
                logging.debug(f"success to receive RTC time calibration from server:{data}")
                try: 
                    
                    for index, data in enumerate(datas): 
                        logging.debug(f"processing the {index} paket")
                        byteData = bytearray.fromhex(data)
                        
                        now = datetime.utcnow()
                        # add 1 minute 3 seconds
                        # future_time = now + timedelta(minutes=0, seconds=0)
                        # byteData = changeDateTime(byteData, future_time)
                        # byteData = changeProbTemperature(byteData, 4.6)
                        print(f'send byte data: {byteData.hex()}')


                        #s.sendall(self.data)
                        s.sendall(byteData)
                        data = s.recv(1024)
                        logging.debug("client received: {}".format(data))

                        '''
                        if True: # send virtual response of command
                            #time.sleep(1)
                            data = s.recv(100)
                            if len(data) > 0: # if command exists? 
                                logging.debug(f'client received command: {data}'); 
                                # send response
                                logging.debug(f'client send command response')
                                s.sendall(self.data_resp)
                        '''
                        time.sleep(0.1)
                    cnt += 1
                    if cnt >= 1: 
                        break
                    

                except socket.timeout: 
                    logging.error("socket clien timout:")
                    s.close()

                except Exception as err: 
                    logging.error("error in client: {}".format(str(err)))
                    break
                time.sleep(1)
                s.close
                break
                
            except KeyboardInterrupt: 
                logging.info("keyboard interrupted")                
                break
            except Exception as err: 
                #logging.error(f"failed in connection: {err}")
                continue


