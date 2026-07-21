"""Multi-device TCP simulator: each logger reports every N seconds."""

from __future__ import annotations

import logging
import random
import socket
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence, Tuple

from client.packet_builder import build_data_packet

socket.setdefaulttimeout(5)


def _range_pair(value: Any, default: Tuple[float, float]) -> Tuple[float, float]:
    if value is None:
        return default
    if isinstance(value, (list, tuple)) and len(value) >= 2:
        return float(value[0]), float(value[1])
    return default


class DeviceState:
    """Per-device sensor state with a gentle random walk."""

    def __init__(
        self,
        serial: str,
        name: str,
        temp_range: Tuple[float, float],
        humi_range: Tuple[float, float],
        batt_range: Tuple[float, float],
    ):
        self.serial = serial
        self.name = name or serial
        self.temp_range = temp_range
        self.humi_range = humi_range
        self.batt_range = batt_range
        self.temperature = random.uniform(*temp_range)
        self.humidity = random.uniform(*humi_range)
        self.battery = random.uniform(*batt_range)
        self.packet_index = random.randint(1, 100)
        self.lock = threading.Lock()

    def next_reading(self) -> Tuple[float, float, float, int]:
        with self.lock:
            self.temperature = self._walk(self.temperature, self.temp_range, 0.15)
            self.humidity = self._walk(self.humidity, self.humi_range, 1.5)
            # battery slowly drains
            self.battery = self._walk(
                self.battery, self.batt_range, 0.05, bias=-0.02
            )
            self.packet_index = (self.packet_index % 9999) + 1
            return (
                round(self.temperature, 1),
                round(self.humidity, 1),
                round(self.battery, 0),
                self.packet_index,
            )

    @staticmethod
    def _walk(
        value: float,
        bounds: Tuple[float, float],
        step: float,
        bias: float = 0.0,
    ) -> float:
        lo, hi = bounds
        nxt = value + random.uniform(-step, step) + bias
        if nxt < lo:
            nxt = lo + random.uniform(0, step * 0.5)
        elif nxt > hi:
            nxt = hi - random.uniform(0, step * 0.5)
        return nxt


class TcpClientSimulate(threading.Thread):
    """
    Simulate many loggers reporting to the TCP server.

    Each device connects, receives UTC calibration, sends one data packet,
    waits for ACK, then disconnects — similar to real GPRS loggers.
    """

    def __init__(
        self,
        devices: Sequence[Dict[str, Any]],
        tcp_host: str,
        tcp_port: int,
        device_cfg: Any,
        interval_sec: float = 300.0,
        stop_event: Optional[threading.Event] = None,
        send_stagger_sec: float = 0.0,
        max_workers: int = 100,
    ):
        super().__init__(daemon=True)
        self.tcp_host = tcp_host
        self.tcp_port = int(tcp_port)
        self.interval_sec = float(interval_sec)
        self.stop_event = stop_event or threading.Event()
        self.send_stagger_sec = float(send_stagger_sec)
        self.max_workers = int(max_workers)

        temp_range = _range_pair(getattr(device_cfg, "temperature", None), (3.0, 7.0))
        humi_range = _range_pair(getattr(device_cfg, "humidity", None), (40.0, 80.0))
        batt_range = _range_pair(getattr(device_cfg, "battery", None), (40.0, 100.0))

        self.states: List[DeviceState] = []
        for item in devices:
            serial = str(item.get("serial") or "").strip()
            if not serial:
                continue
            self.states.append(
                DeviceState(
                    serial=serial,
                    name=str(item.get("name") or serial),
                    temp_range=temp_range,
                    humi_range=humi_range,
                    batt_range=batt_range,
                )
            )

        logging.info(
            f"simulate {len(self.states)} devices -> {self.tcp_host}:{self.tcp_port} "
            f"every {self.interval_sec}s"
        )

    def _send_one(self, state: DeviceState) -> bool:
        temp, humi, batt, idx = state.next_reading()
        now = datetime.utcnow()
        packet = build_data_packet(
            serial=state.serial,
            temperature=temp,
            humidity=humi,
            battery=batt,
            dt=now,
            packet_index=idx,
            csq=random.randint(12, 31),
            light=random.randint(0, 200),
        )

        sock = None
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            sock.settimeout(5)
            sock.connect((self.tcp_host, self.tcp_port))
            # server sends @UTC,...# on connect
            try:
                sock.recv(128)
            except socket.timeout:
                pass

            sock.sendall(packet)
            try:
                ack = sock.recv(1024)
                logging.debug(f"{state.serial} ack={ack!r}")
            except socket.timeout:
                logging.warning(f"{state.serial}: no ACK received")

            logging.info(
                f"sent {state.serial} ({state.name}) "
                f"T={temp}C H={humi}% B={batt}% idx={idx} "
                f"utc={now.strftime('%Y-%m-%d %H:%M:%S')}"
            )
            return True
        except Exception as err:
            logging.error(f"failed to send {state.serial}: {err}")
            return False
        finally:
            if sock is not None:
                try:
                    sock.close()
                except Exception:
                    pass

    def _report_round(self) -> None:
        logging.info(f"report round start: {len(self.states)} devices")
        ok = 0
        if self.max_workers <= 1 or self.send_stagger_sec > 0:
            for state in self.states:
                if self.stop_event.is_set():
                    break
                if self._send_one(state):
                    ok += 1
                if self.send_stagger_sec > 0:
                    self.stop_event.wait(self.send_stagger_sec)
        else:
            max_workers = min(self.max_workers, len(self.states) or 1)
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {executor.submit(self._send_one, state): state for state in self.states}
                for future in as_completed(futures):
                    if self.stop_event.is_set():
                        break
                    try:
                        if future.result():
                            ok += 1
                    except Exception as err:
                        state = futures[future]
                        logging.error(f"unexpected error sending {state.serial}: {err}")
        logging.info(f"report round done: {ok}/{len(self.states)} ok")

    def run(self) -> None:
        if not self.states:
            logging.error("no devices to simulate")
            return

        # first report immediately, then every interval
        while not self.stop_event.is_set():
            started = time.monotonic()
            self._report_round()
            elapsed = time.monotonic() - started
            wait = max(0.0, self.interval_sec - elapsed)
            logging.info(f"next report in {wait:.0f}s")
            if self.stop_event.wait(wait):
                break

        logging.info("simulate client stopped")
