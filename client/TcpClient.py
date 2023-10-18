from threading import Thread
from multiprocessing import Event
import os
import json
import logging
import socket
import time
from datetime import datetime
from signal import signal, SIG_DFL, SIG_IGN

socket.setdefaulttimeout(3)


class TcpClient(Thread): 
    def __init__(self, cfg, stop_flag:Event): 
        super().__init__()
        self.cfg = cfg
        self.flag = stop_flag
        self.server = cfg.server
        self.port = int(self.cfg.port)
        self.data = bytearray.fromhex(self.cfg.data)


    def run(self): 
        logging.debug("starting tcp client")
        cnt = 0
        while True: 
            try: 
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
                s.settimeout(4)
                s.connect((self.server, self.port))
                # receive time calibration data
                data = s.recv(128)
                logging.debug(f"success to receive RTC time calibration from server:{data}")
                try: 
                    # send data packet
                    s.sendall(self.data)
                    data = s.recv(1024)
                    logging.debug("client received: {}".format(data))
                    cnt += 1
                    if cnt >= 5: 
                        break
                except socket.timeout: 
                    logging.error("socket clien timout:")

                except Exception as err: 
                    logging.error("error in client: {}".format(str(err)))
                    break
                time.sleep(1)
                
            except KeyboardInterrupt: 
                logging.info("keyboard interrupted")                
                break
        


