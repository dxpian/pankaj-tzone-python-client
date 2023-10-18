import os
import re
import logging
from logging.handlers import TimedRotatingFileHandler
from datetime import datetime
from termcolor import colored

# initialize global logger
def init_logger(logName = 'App.log'):
    os.makedirs('Log', exist_ok=True)
    FORMAT = "[%(levelname)s %(filename)s:%(lineno)s - %(funcName)s() %(asctime)s ]: %(message)s"
    #logging.basicConfig(filename='Log/{}'.format(logName), level=logging.DEBUG, filemode='w', format=FORMAT, datefmt='%d-%b-%y %H:%M:%S')
    logging.basicConfig(level=logging.DEBUG,  format=FORMAT, datefmt='%d-%b-%y %H:%M:%S')
    logging.debug('System successfully launched')

# init logger of engine
def getLogger(logFileName):

    logLevel = logging.DEBUG
    os.makedirs('Log', exist_ok=True)
    logger = logging.getLogger('TzoneLogger-{}'.format(logFileName))
    logger.setLevel(logLevel)

    logFileName = logFileName + ".log"
    log_format = "[%(levelname)s %(filename)s:%(lineno)s - %(funcName)s() %(asctime)s ]: %(message)s"
    handler = TimedRotatingFileHandler("Log/{}".format(logFileName), when="midnight", interval=2)
    handler.setLevel(logLevel)
    formatter = logging.Formatter(log_format)
    handler.setFormatter(formatter)

    # add a suffix which you want
    handler.suffix = "%Y%m%d"

    # need to change the extMatch variable to match the suffix for it
    handler.extMatch = re.compile(r"^\d{8}$")

    # finally add handler to logger
    logger.addHandler(handler)
    return logger

# return formatted time string
def getTimeFormatString():
    now = datetime.now()
    timeStr = now.strftime("%Y-%m-%d %H-%M-%S")
    return timeStr

def logErrMessage(message):
    logging.error(message)
    print(colored(message, 'red'))

def logInfoMessage(message):
    logging.info(message)
    print(colored(message, 'green'))

def logDebugMessage(message):
    logging.debug(message)
    print(colored(message, 'yellow'))