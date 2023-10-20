import multiprocessing as mp
import os, sys
import logging
from server.TcpServer import TcpServer
from client.TcpClient import TcpClient
from config.readconfig import get_hparams_from_commentjson
from utils.logutil import init_logger


if __name__ == "__main__":
    init_logger(terminal=True)
    cfgfile =  "config/config_server.json"
    if not os.path.isfile(cfgfile): 
        logging.error("cannot find config file: {}".format(cfgfile))
        sys.exit(0)
    logging.info(f"loading configuration from {cfgfile}")
    stop_server = mp.Event()
    cfg = get_hparams_from_commentjson(cfgfile)
    server = TcpServer(cfg.server, stop_server)
    server.start()
    server.join()
    logging.info("exiting system")
