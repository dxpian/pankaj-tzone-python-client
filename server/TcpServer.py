import multiprocessing as mp
import logging
from threading import Thread
import socket
from datetime import datetime
import logging
import time

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
                logging.debug(f"server received data, response same: {data}")
                # analyze data packet
                if self.analyze_packet(data): 
                    logging.info("success to parse data packet")
                else: 
                    logging.error("failed to parse data packet")
                # send ack data
                response = f"@ACK,{hex(11)}#"
                conn.sendall(bytes(data, "utf-8"))

            except Exception as err: 
                logging.error(f"error in incomming connection: {addr}: {err}")
                break
        conn.close()
        logging.info("Exit thread task. connection closed")
        
    def analyze_packet(self, data:bytes): 
        ll = len(data)
        logging.debug(f"received packet length: {ll}")

        logging.debug("checking header packet")
        if data[0] != 0x54 and data[1] != 0x5A: 
            logging.error("Invalid header packet")
            return False
        '''
        ‘T’ ‘Z’
        Tzone company identifier. This is the header of every packet
        '''
        start_bits = bytes[0:2]
        '''
        The bytes length from the start at protocol number to the end at the CRC.
        '''
        packet_lenth = bytes[2:4]
        '''
        $$
        Normal data
        '''
        commandTypeId = bytes[4:6]
        '''
        0x04 0x0A
        The hardware is TT19
        '''
        hardwareType = bytes[6:8]
        '''
        Each byte represents a first-level version
        For example, 01H 01H 00H 00H indicates that the version is 1.1.0.0
        '''
        Firmware = bytes[8:12]
        '''
        The high four bits of the first byte are ignored, and every other 4 bits represent a character, 
        such as 01H 90H 02H 30H 00H 00H 00H 02H Indicates that the IMEI is 190023000000002.
        '''
        IMEI= bytes[12:20]
        '''
        The time when the piece of data is packaged and ready to be sent is in the order of year, month, day, hour, minute, and second, and 2000 is added to the year. 
        For example, 17H 08H 01H 09H 37H 09H indicates that the time is: 2023/08/01 17:55:09
        '''
        rtcTime = bytes[20:26]
        '''
        Indicates the length of GPS information (unit: byte), if it is 0000H, it means that there is no such data
        '''
        gpsDataLen = bytes[26:28]
        '''
        bit0: latitude mark, 
            1=N north latitude, 
            0=S south latitude; 
        bit1: longitude  mark, 
            1=W west longitude, 
            0=E
        east longitude, other bits are reserved
        '''
        status = bytes[28:29]
        '''
        The format is the same as the RTC date time
        '''
        utcTime = bytes[29:35]
        '''
        Unit: 0.000001 degree, HEX format, this value/1000000 is the longitude, 
        such as 015976CAH means 22.640330
        '''
        latitude = bytes[35:39]
        '''
        Unit: 0.000001 degree, HEX format, this value/1000000 is the latitude,
        such as 06CB9E5AH means 114.007642
        '''
        longitude = bytes[39:43]
        '''
        Unit: degree, reserved
        '''
        angle = bytes[43:45]
        '''
        Unit: 0.1Knots, reserved,such as 0001H means 0.1Knots，which is 0.1852km/h
        '''
        speed = bytes[45:47]
        '''
        GSM LBS’s data length excludes LBS data length part. 
        If the value is 0, there is no LBS data.
        '''
        lbs_data_len = data[47:49]
        '''
        The number of LSB base stations included in this package data
        '''
        lbs_number = data[49:50]
        '''
        Single LBS base station information length and base station information indication,
        bit7-5:  means base station type,
            000H-2G base station, 
            010H-NB base station , 
            100H-CATM1 base station , 
            110H-LTE base  station ;
        bit4-0 ,means Signal LBS information length
        '''
        lbs_signal = data[50:51]
        '''
        Mobile Country Code, ignore the first digital, only 3 digital, 04 60 means that MCC is 460.
        '''
        mobile_country_code = data[51:53]
        '''
        Mobile Network Code, 2 or 3 digital, 
        if the first digital is 8 , MNC is 3 digital. 
        If the first digital is 0, MNC is 2 digital.
        87 56 means that MNC is 756. 00 56 means 56.
        '''
        mobile_network_code = data[53:55]
        '''
        location area code, hex code. 0x27 0x56 means LAC is 10070
        '''
        localtion_area_code = data[55:57]
        '''
        Cell identification code, 4 byte, hex code, i.e. 01H23H45H67H means CELL ID is 19088743;
        In the data example:
        LBS length:00H 22H, means 34byte;
        The number of LBS：03H, means 3;
        The first LBS information:
        Signal LBS information :0AH，2G base station，Contains
        10 bytes of data;
        MCC :04H 60H,460;
        MNC:00H 00H,00；;
        LAC:27H 93H,10131;
        CELL ID:00H 00H 0FH A1H,4001;
        The second LBS information:
        Signal LBS information:0AH,2G base station,Contains
        10 bytes of data;
        MCC:04H 60H,460;
        MNC:00H 00H,00;
        LAC:27H B6H,10166;
        CELL ID:00H 00H 15H BBH,5563;
        The Third LBS information:
        Signal LBS information:0AH，2G base station，Contains
        10 bytes of data;
        MCC:04H 60H,460;
        MNC:00H 00H,00;
        LAC:27H B6H,10166;
        CELL ID:00H 00H 12H A3H,4771;
        '''
        cell_id = data[57:61]
        '''
        Received Signal power, 1 byte, hex format, unit: -dbm, supported by 2G base stations, 
        this data does not appear for unsupported base stations; for example, 52H means -82dbm
        '''
        rxRev = data[61:62]
        phy_cell_id = data[62:64]
        '''
        Evolved Absolute Radio Frequency Channel, 3 bytes, hex format, supported by LTE base stations.
        this data will not appear for unsupported base stations
        '''
        earfcn = data[64:67]        
        '''
        Reference Signal Received Power (RSRP) in dBm.
        1 byte, hex format, unit: -dbm, supported by LTE base stations, this data does not appear for unsupported base stations, such as 52H means -82dbm
        '''
        RSRP = data[67:68]
        '''
        Reference Signal Received Quality (RSRQ) in dB.1 byte, hex format, unit: -db, supported by LTE base stations,
        this data does not appear for unsupported base stations, such as 12H means -18db
        '''
        RSRQ = data[68:69]
        '''
        Received signal strength indicator value, 1 byte, hex format, unit: -dbm, supported by LTE base stations, 
        this data does not appear for unsupported base stations, such as 52H means -82dbm
        '''
        RSSI = data[69:70]
        '''
        The status data length excluding “Status data length” itself. If this part is 0, there is no status data.
        '''
        status_data_len = data[70:72]
        '''
        The value of this part has four possibilities, Temperature/humidity included in all the data. 0xAA Interval GPRS data
        0x10 Low battery Alarm
        0xA0 Temperature/Humidity over threshold alarm
        0xA1 Temperature/Humidity sensor abnormal alarm
        0xA2 Light sensor bright and dark changes
        0xA3 Shock alarm
        0xB0 Turn on the device
        0xB1 Turn off the device
        '''
        alarm_type = data[72:73]
        '''
        Bit 7-6 work mode
            00= Normal work mode, 01= Flight mode,
        bit 5 are reserved for future use. 
        Bit4:   1 press the button
                0 Have not press the button
        Bit3:   1 The temperature/Humidity sensor is abnormal
                0 The temperature/Humidity sensor is normal
        Bit2:   1 The temperature/Humidity is over threshold
                0 The temperature/Humidity is normal
        Bit1:   1 The battery low voltage
                0 The battery is normal
        Bit0:   1 The machine is charging
                0 The machine is not charging
        '''
        thermal_info = data[73:74]
        #CSQ value , Hex code
        gms_signal_len = data[74:75]
        '''
        Bit 7 to bit 6 are reserved for future use.
        Bit 5:  1 Internet connection is established
                0 Internet connection is not established
        Bit4:   1 GPRS is registered successfully
                0 GPRS is not registered
        Bit3:   1 The GSM is in roaming mode
                0 The GSM is in home network mode
        Bit2:   1 GSM is registered successfully
                0 GSM is not registered yet
        Bit1:   1 Detected SIM card
                0 Not detected SIM card
        Bit0:   1 The GSM module is started
                0 The GSM module is not started yet
        '''
        gsm_status = data[75:76]
        '''
        Unit:10mv, for example: 0175H=373(DEC), 375*10mV=3.73V.
        '''
        battery_voltage = data[76:78]
        '''
        unit 0.1℃,2byte，need convert to binary;
        bit15: 
            means if the built-in sensor is normal,
            0 means normal，1 means abnormal；
        bit14:
            means temperature is positive or negative , 
            0 means positive，1 means negative;
        bit 0 to bit13 :
            means temperature value, need convert to decimal.
            For example, 0142H means temperature 32.2℃，412E means temperature -30.2℃ ， 
            8000 means temperature sensor abnormal ；
        different devices type please refer to different data
        description.
        '''
        builtin_temperature = data[78:80]
        '''
        unit 0.1%，2byte，need covert to binary,;
        bit15 : 
            means if the built-in sensor is normal, 
            0 means normal，1 meams abnormal;
        bit0 to 14:
            means RH value，need covert to decimal. 
            For example, 028BH means humidity 65.1%，
            8000 means built-in sensor abnormal;
        different devices type please refer to different data description.
        '''
        builtin_humidity = data[80:82]
        '''
        unit 0.1℃,2byte，need convert to binary;
        bit15 : 
            means if the built-in sensor is normal,
            0 means normal，1 means abnormal；
        bit14: 
            means temperature is positive or negative , 
            0 means positive，1 means negative;
        bit0to bit13: 
            means temperature value, need convert to decimal. 
        different devices type please refer to different data description.
        '''
        external_temp = data[82:84]
        '''
        unit 0.1%，2byte，need covert to binary;
        bit15: 
            means if the built-in sensor is normal, 
            0 means normal，1 meams abnormal;
        bit0 to 14: 
            means RH value，need covert to decimal. 
            different devices type please refer to different data description.
        '''
        external_humidity = data[84:86]
        '''
        2byte，unit：lux ,need convert to decimal
        '''
        light_sensor = data[86:88]
        '''
        2byte，unit：mg, need convert to decimal
        '''
        shock_sensor = data[88:90]
        '''
        2 bytes， need convert to decimal， if it is 0000 means without WIFI data；
        '''
        wifi_data_len = data[90:92]
        '''
        6 bytes， for example, 36 C2 E4 E2 6E 63 means the WIFI AP mac address is 36:C2:E4:E2:6E:63
        '''
        single_wifi_ap_mac = data[92:98]
        '''
        1byte，need convert to decimal，unit：-dbm
        '''
        signle_wifi_rssi = data[98:99]
        '''
        The value range of this part is between 1 and 9999
        '''
        packet_index = data[99:101]
        '''
        The checked content is from the “protocol number” to the end at “CRC”, 
        including “protocol number”, excluding “CRC”.
        '''
        crc = data[101:103]
        '''
        0x0D 0x0A
        Indicate that this packet is finished
        '''
        stop_bit = data[103:105]