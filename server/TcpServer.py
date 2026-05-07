import multiprocessing as mp
import logging
from threading import Thread
import socket
from datetime import datetime
import logging
import time
from utils.deviceDefine import Packet
class TcpServer(Thread): 
    def __init__(self, args, stop_flag: mp.Event ) -> None:
        super().__init__()
        self.cfg = args
        self.server = args.server
        self.port = args.port
        self.flag = stop_flag

    def run(self): 
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((self.server, self.port))
        s.listen(5)
        while True: 
            if self.flag.is_set(): 
                logging.debug("exiting server")
                break
            try:
                logging.debug("server listening at {}".format(self.port))
                conn, addr = s.accept()
            except Exception as err: 
                time.sleep(0.01)
                continue
            trd = Thread(target=self.process_client, args=(conn, addr))
            trd.start()
        s.close()
            
    def process_client(self, conn, addr): 
        logging.debug(f"Connected by {addr}")
        strtime = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        response = f"@UTC,{strtime}#"
        conn.sendall(bytes(response, "utf-8"))
        while True:
            try: 
                data = conn.recv(1024)
                if not data:
                    break
                logging.debug(f"server received data: {data.hex()}")
                
                # analyze data packet
                packet = Packet()
                if self.analyze_packet(data, packet): 
                    logging.info("success to parse data packet")
                    # send reply
                    packet_index = packet.packet_index
                    response = f"@ACK,{packet_index}#"
                    logging.info("sending response: {}".format(response))
                    conn.sendall(bytes(response, "utf-8"))
                    command = '@CMD,*000000,201,55#,#'
                    logging.info(f"sending command: {command}")
                    conn.sendall(bytes(command), 'utf-8')
                else: 
                    logging.error(f"failed to parse data packet: {data}")
                
                

            except Exception as err: 
                logging.error(f"error in incomming connection: {addr}: {err}")
                break
        conn.close()
        logging.info("Exit thread task. connection closed")
    
    '''
    function: analyze_packet
    description: analyze packet data
    return: True if success
    '''
    def analyze_packet(self, data:bytes, packet: Packet): 
        ll = len(data)
        logging.debug(f"received packet length: {ll}")
        result = packet.analyze_packet(data)
        return result

        