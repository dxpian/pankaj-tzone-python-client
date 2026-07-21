"""
Entrypoint: fetch all devices from the server API, save as JSON,
then simulate each logger reporting every 5 minutes over TCP.
"""

import argparse
import logging
import os
import sys
import threading

from client.device_fetcher import (
    fetch_all_devices,
    load_devices_json,
    save_devices_json,
)
from client.TcpClientSimulate import TcpClientSimulate
from config.readconfig import get_hparams_from_commentjson
from utils.logutil import init_logger


DEFAULT_CFG = "config/config_server.json"
DEFAULT_DEVICES_FILE = "Log/devices.json"


def _cfg_get(obj, key, default=None):
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Simulate multiple TZ loggers reporting to the TCP server."
    )
    parser.add_argument(
        "--config",
        default=DEFAULT_CFG,
        help=f"config file path (default: {DEFAULT_CFG})",
    )
    parser.add_argument(
        "--devices-file",
        default=None,
        help="path to save/load device list JSON",
    )
    parser.add_argument(
        "--skip-fetch",
        action="store_true",
        help="skip API fetch and load devices from --devices-file",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=None,
        help="report interval seconds (default: 300 / config simulate.interval_sec)",
    )
    parser.add_argument(
        "--send-stagger",
        type=float,
        default=None,
        help="stagger seconds between sequential sends (default: 0 / config simulate.send_stagger_sec)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=None,
        help="maximum parallel worker threads for sending devices (default: 100 / config simulate.max_workers)",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="send one report round then exit",
    )
    args = parser.parse_args()

    init_logger(terminal=True)

    if not os.path.isfile(args.config):
        logging.error(f"cannot find config file: {args.config}")
        return 1

    cfg = get_hparams_from_commentjson(args.config)
    server_cfg = _cfg_get(cfg, "server")
    device_cfg = _cfg_get(cfg, "device")
    simulate_cfg = _cfg_get(cfg, "simulate")

    devices_file = (
        args.devices_file
        or _cfg_get(simulate_cfg, "devices_file", DEFAULT_DEVICES_FILE)
    )
    interval_sec = args.interval
    if interval_sec is None:
        interval_sec = float(_cfg_get(simulate_cfg, "interval_sec", 300))
    send_stagger_sec = args.send_stagger
    if send_stagger_sec is None:
        send_stagger_sec = float(_cfg_get(simulate_cfg, "send_stagger_sec", 0.0))
    max_workers = args.workers
    if max_workers is None:
        max_workers = int(_cfg_get(simulate_cfg, "max_workers", 100))

    tcp_host = _cfg_get(server_cfg, "server", "localhost")
    tcp_port = int(_cfg_get(server_cfg, "port", 18801))
    token = _cfg_get(server_cfg, "token", "")
    api_url = _cfg_get(server_cfg, "api_url", "http://localhost:9000/api")

    if args.skip_fetch:
        logging.info(f"loading devices from {devices_file}")
        devices = load_devices_json(devices_file)
    else:
        if not token:
            logging.error("server.token is empty in config")
            return 1
        try:
            devices = fetch_all_devices(api_url=api_url, token=token)
            save_devices_json(devices, devices_file)
        except Exception as err:
            logging.error(f"failed to fetch devices: {err}")
            if os.path.isfile(devices_file):
                logging.warning(f"falling back to cached {devices_file}")
                devices = load_devices_json(devices_file)
            else:
                return 1

    if not devices:
        logging.error("device list is empty")
        return 1

    logging.info(f"simulating {len(devices)} devices")

    stop_event = threading.Event()
    client = TcpClientSimulate(
        devices=devices,
        tcp_host=tcp_host,
        tcp_port=tcp_port,
        device_cfg=device_cfg,
        interval_sec=interval_sec,
        stop_event=stop_event,
        send_stagger_sec=send_stagger_sec,
        max_workers=max_workers,
    )

    if args.once:
        client._report_round()
        return 0

    client.start()
    try:
        while client.is_alive():
            client.join(timeout=1.0)
    except KeyboardInterrupt:
        logging.info("keyboard interrupt, stopping...")
        stop_event.set()
        client.join(timeout=10.0)

    logging.info("exiting simulate")
    return 0


if __name__ == "__main__":
    sys.exit(main())
