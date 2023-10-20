import logging
from utils.byteutils import byte_to_int
from utils.logutil import init_logger
from utils.deviceDefine import Packet

init_logger()
data_str = "545A00592424040A010300000190023000000095170A140228390000001401D204600011ED240FC9EBD101ED000096590345000EAA00153F006400E4018F001A00000015BC5FF6A7A1B9411C88795932114E4C7766E6944A51001729130D0A"
data = bytearray.fromhex(data_str)
packet = Packet()
result = packet.analyze_packet(data)

if result: 
    logging.info("success to analyze packet data")
    # send reply
    packet_index = packet.packet_index
    response = f"@ACK,{packet_index}#"
    logging.info("sending response: {}".format(response))
else: 
    logging.error("Failed to analyze packet data")



