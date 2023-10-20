import logging
from collections import defaultdict
from utils.byteutils import *
from datetime import datetime
import time

class HardwareType: 
    TT19 = 'TT19'
    UNK = "UNK"

# check hardware type checker
class HardwareTypeChecker: 
    def __init__(self) -> None:
        # define harware type
        self.datas = defaultdict(lambda: list)
        self.datas[HardwareType.TT19] = ['040A', '040B', '040C', '040D', '040E']
        self.datas[HardwareType.UNK] = []
        
    '''
    check if hardware type is valid. 
    param: 
        @strtype: 040a, ... for TT19
    '''
    def check(self, strtype: str)->str: 
        strtype = strtype.upper()
        for hard_name, hard_type in self.datas.items(): 
            if strtype in hard_type: 
                return hard_name
        return HardwareType.UNK

class WiFi: 
    def __init__(self, mac:str, rssi: int) :
        self.mac = mac
        self.rssi = rssi
    def __str__(self) -> str:
        expression = f'MAC: {self.mac}(RSSI={self.rssi}db)'
        return expression

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
def check_alamr_type(data: bytes): 
    _type = "UNK"
    alam = int.from_bytes(data)
    if alam == 0x10: 
        _type = "Low battery alarm"
    elif alam == 0xA0: 
        _type = "Temperature/Humidity over threshold alarm"
    elif alam == 0xA1: 
        _type = "Temperature/Humidity sensor abnormal alarm"
    elif alam == 0xA2: 
        _type = "Light sensor bright and dark changes"
    elif alam == 0xA3: 
        _type = "Shock alarm"
    elif alam == 0xB0: 
        _type = "Turn on the device"
    elif alam == 0xB1: 
        _type = "Turn off the device"
    return _type

# tzond data packet define class
class Packet:
    def __init__(self) -> None:
        self.startbits = ""     # TZ
        self.packet_len = 0     # The bytes length from the start at protocol number to the end at the CRC.
        self.protocol_number = ""       # $$
        self.hardware_type = bytes()    # "040A" for tt19, b('\x04\n')
        self.firmware_version = "0.0"   # firmware version
        self.imei = ""                  # imei number
        self.rtctime = ""               # rtc time
        self.gps_data_len = 0           #Indicates the length of GPS information (unit: byte), if it is 0000H, it means that there is no such data
        self.status = 0                 # 
        self.utc_time = ""              # The format is the same as the RTC date time
        self.latitude = 0.0             # Unit: 0.000001 degree, HEX format, this value/1000000 is the longitude, such as 015976CAH means 22.640330
        self.longitude = 0.0            # Unit: 0.000001 degree, HEX format, this value/1000000 is the latitude, such as 06CB9E5AH means 114.007642
        self.angle = 0.0                # reserved
        self.speed = 0.0                # Unit: 0.1Knots, reserved,such as 0001H means 0.1Knots，which is 0.1852km/h
        self.lbs_data_len = 0           # GSM LBS’s data length excludes LBS data length part. If the value is 0, there is no LBS data.
        self.lbs_number = 0             # The number of LSB base stations included in this package data
        self.signal_lbs_type = ''               # Single LBS base station information length and base station information indication
        self.signal_lbs_info_len = 0
        self.mcc = 0                    # Mobile Country Code
        self.mnc = 0                    # Mobile Network Code
        self.lac = 0                   # location area code, hex code
        self.cell_id = b''        # Cell identification code
        self.RxLev = 0
        self.pci = b''             #Physical Cell Identity, 2 bytes, hex format, supported by LTE base stations, this data does not appear for unsupported base stations 
        self.earfcn = b''         # Evolved Absolute Radio Frequency Channel, 3 bytes, hex format
        self.rsrp = 0                   # Reference Signal Received Power (RSRP) in dBm.1 byte, hex format, unit: -dbm,
        self.rsrq = 0                   # Reference Signal Received Quality (RSRQ) in dB.1 byte, hex format, unit: -db
        self.rssi = 0                   # Received signal strength indicator value, 1 byte, hex format, unit: -dbm
        self.status_data_len = 0        # The status data length excluding “Status data length” itself. If this part is 0, there is no status data
        self.alarm_type = 0             # The value of this part has four possibilities, Temperature/humidity included in all the data
        self.terminal = 0
        self.gms_signal_strength = 0    # CSQ value , Hex code
        self.gsm_status = 0             # 
        self.battery_voltage = 0        # Unit:10mv, for example: 0175H=373(DEC), 375*10mV=3.73V.
        self.builtin_temperature = 0.0           # unit 0.1℃,2byte，need convert to binary;
        self.builtin_humidity = 0       # unit 0.1%，2byte，need covert to binary,
        self.external_temperature =0.0  # unit 0.1℃,2byte，need convert to binary;
        self.external_temperature2 = 0.0# unit 0.1℃,2byte，need convert to binary
        self.external_humidity = 0.0    # unit 0.1%，2byte，need covert to binary;
        self.light_sensor = 0           # 2byte，unit：lux ,need convert to decimal
        self.shock_sensor = 0           # 2byte，unit：mg, need convert to decimal
        self.wifi_data_len = 0          # 2 bytes， need convert to decimal， if it is 0000 means without WIFI data；
        self.wifi = []                  # list of WiFi 
        self.packet_index = 0           #  The value range of this part is between 1 and 9999
        self.crc = 0                    #  The checked content is from the “protocol number” to the end at “CRC”, including “protocol number”, excluding “CRC”.
        self.stop = b''                 # 0x0d0a

    '''
    2 bytes
    Tzone company identifier. This is the header of every
    packet
    '''
    def set_start_bites(self, data:bytes): 
        self.startbits = data.decode("utf-8").upper()
        logging.debug(f'start bits: {self.startbits}')
        if self.startbits != 'TZ': 
            return False
        return True

    '''
    2 byttes: 
    The bytes length from the start at protocol number to the end at the CRC.
    '''
    def set_packet_length(self, data:bytes): 
        if len(data) != 2: 
            logging.error("Invalid packet length data format")
        data_len = byte_to_int(data)
        self.packet_len = data_len + 6 # 2: start, 2: packet_len, 2: stop bits
        logging.debug(f'packet length: {self.packet_len}')
    
    # 2 bytes. set protocol number: it should be "$$"
    def set_protocol_number(self, data:bytes): 
        if len(data) != 2: 
            logging.error("Invalid protocol number data format")
        self.protocol_number = data.decode("utf-8")
        logging.debug("protocol number: {}".format(self.protocol_number))

    '''
    2 bytes
     The hardware is TT19
     040a, 040b,040c, 040d,040e for TT19
    '''
    def set_hardware_type(self, data: bytes): 
        if len(data) != 2: 
            logging.error('Invalid hardware type data format')
        self.hardware_type = data.hex()
        checker = HardwareTypeChecker()    
        logging.debug("hardwaretype = {}".format(checker.check(self.hardware_type)))

    '''
    4 bytes
    Each byte represents a first-level version
    For example, 01H 01H 00H 00H indicates that the
    version is 1.1.0.0
    '''
    def set_firmware_version(self, data:bytes): 
        if len(data) != 4: 
            logging.error("Invalid firmware version data format")
        version_list = []
        for b in data: 
            version_list.append(f'{int(b):02}')
        self.firmware_version = '.'.join(version_list)
        logging.debug(f"firmware version = {self.firmware_version}")

    '''
    8 bytes
    The high four bits of the first byte are ignored, and every
    other 4 bits represent a character, such as 01H 90H 02H
    30H 00H 00H 00H 02H
    Indicates that the IMEI is 190023000000002
    '''
    def set_imei(self, data: bytes): 
        if len(data) != 8: 
            logging.error("invalid imei data format")
        imei = data.hex()
        # ignore first 4 bit(one charactor)
        self.imei = imei[1:]
        logging.debug(f"imei: {self.imei}")

    '''
    6 bytes: 
    The time when the piece of data is packaged and ready to be sent is in the order of 
    year, month, day, hour, minute, and second, and 2000 is added to the year. For example, 17H 08H 01H 09H 37H 09H indicates that
    the time is: 2023/08/01 17:55:09
    '''
    def set_rtc_time(self, data: bytes): 
        if len(data) != 6: 
            logging.error("Invalid rtc time format")
            return
        y = data[0] + 2000
        m = data[1]
        d = data[2]
        H = data[3]
        M = data[4]
        S = data[5]
        self.rtctime = f'{y:04}-{m:02}-{d:02} {H:02}:{M:02}:{S:02}'
        logging.debug(f"rtc time: {self.rtctime}")

    '''
    6 bytes. same as rtc time
    '''
    def set_utc_time(self, data:bytes): 
        if len(data) != 6: 
            logging.error("Invalid rtc time format")
            return
        y = data[0] + 2000
        m = data[1]
        d = data[2]
        H = data[3]
        M = data[4]
        S = data[5]
        self.utc_time = f'{y:04}-{m:02}-{d:02} {H:02}:{M:02}:{S:02}'
        logging.debug(f"rtc time: {self.rtctime}")

    '''
    set latitude/longitude data
    params: 
        @status: 1 bytes: 
            bit0: latitude mark, 
                1=N north latitude, 
                0=S south latitude; 
            bit1: longitude  mark, 
                1=W west longitude, 
                0=E east longitude,
            other bits are reserved
        @latitude: 4 bytes: 
            Unit: 0.000001 degree, HEX format, this value/1000000 is the longitude, such as 015976CAH means 22.640330
        @longitude: 4 bytes: 
            Unit: 0.000001 degree, HEX format, this value/1000000 is the latitude, such as 06CB9E5AH means 114.007642
    '''
    def set_gps(self, status: bytes, latitude: bytes, longitude: bytes): 
        if len(status) != 1 or len(latitude) != 4 or len(longitude) != 4: 
            logging.error("Invalid GPS data")
            return

        status = int.from_bytes(status)
        status_lat = "N" if (int(status) & 0x01) else "S" # 
        status_lan = "E" if (int(status) & 0x02) else "E"

        self.latitude = int.from_bytes(latitude) / 1000000.0
        self.longitude = int.from_bytes(longitude) / 1000000.0
        logging.debug(f"{status_lat} latitude: {self.latitude},  {status_lan} longitude = {self.longitude}")

    '''
    12 byte reserved data
    '''
    def set_direction(self, data): 
        if len(data) != 2: 
            logging.error("Invalid angle data format")
            return
        self.angle = int.from_bytes(data)
        logging.debug("direction: {}".format(self.angle))

    '''
    2 bytes
    Unit: 0.1Knots, reserved,such as 0001H means 0.1Knots，which is 0.1852km/h
    '''
    def set_speed(self, data: bytes): 
        if len(data) != 2: 
            logging.error("Invalid speed data format")
            return 
        self.speed = int.from_bytes(data) * 0.1
        logging.debug("speed: {} knots".format(self.speed))

    '''
    2 bytes: 
    GSM LBS’s data length excludes LBS data length part. If
    the value is 0, there is no LBS data.
    '''
    def set_lbs_data_len(self, data: bytes): 
        if len(data) != 2: 
            logging.error("Invalid LBS data len format")
            return 
        self.lbs_data_len = int.from_bytes(data)
        logging.debug("lbs data len = {}".format(self.lbs_data_len))
    
    '''
    1 bytes: 
    The number of LSB base stations included in this
    package data
    '''
    def set_lbs_number(self, data: bytes): 
        if len(data) != 1: 
            logging.error("Invalid LBS number format")
            return
        self.lbs_number = int.from_bytes(data)
        logging.debug("lbs number: {}".format(self.lbs_number))

    '''
    l byte
    Single LBS base station information length and base station information indication,
    bit7-5:  means base station type,
        000H-2G base station, 
        010H-NB base station , 
        100H-CATM1 base station , 
        110H-LTE base  station ;
    bit4-0 ,means Signal LBS information length
    '''
    def set_lbs_signal(self, data: bytes): 
        data = int.from_bytes(data)
        station_type = data >> 5
        _type = "unk"
        if station_type == 0x00: 
            _type = "2G"
        elif station_type == 0x02: 
            _type = "NB"
        elif station_type == 0x04: 
            _type = "CATM1"
        elif station_type == 0x06: 
            _type = "LTE"
        self.signal_lbs_info_len = data & 0xe0
        self.signal_lbs_type = _type
        logging.info(f"lbs type = {_type}, lbs info len = {self.signal_lbs_info_len}",)
    
    '''
    2 bytes
    Mobile Country Code, ignore the first digital, only 3 digital, 04 60 means that MCC is 460.
    '''
    def set_mobile_code(self, data:bytes): 
        if len(data) != 2: 
            logging.error("Invalid mobile country code")
            return
        str_mcc = data.hex()
        try: 
            mcc = int(str_mcc)
        except ValueError: 
            logging.error("Invalid MCC code: {}".format(str_mcc))
            return
        self.mcc = mcc % 1000  # valid only 3 number
        logging.debug("Mobile country code: {}".format(self.mcc))

    '''
    2 bytes: 
    Mobile Network Code, 2 or 3 digital, 
    if the first digital is 8 , MNC is 3 digital. If the first digital is 0, MNC is 2 digital.
    87 56 means that MNC is 756. 00 56 means 56.
    '''
    def set_mobile_network_code(self, data: bytes): 
        if len(data) != 2: 
            logging.error("Invalid mobile network code data format")
            return
        str_code = data.hex()
        if len(str_code) != 4: 
            logging.error("Invalid mobile network code data format")
            return
        if str_code[0] == '8': 
            self.mnc = int(str_code[1:])
        elif str_code[0] == '0': 
            self.mnc = int(str_code[2:])
        logging.debug(f"Mobile network code: {self.mnc}")
    
    '''
    2bytes:
    location area code, hex code. 0x27 0x56 means LAC is 10070
    '''
    def set_location_area_code(self, data: bytes): 
        if len(data) != 2: 
            logging.error("Invalid Location area code")
            return
        self.lac = int.from_bytes(data)
        logging.info(f"location area code: {self.lac}")
    
    '''
    1 bytes
    The value of this part has four possibilities, Temperature/humidity included in all the data. 0xAA Interval GPRS data
    0x10 Low battery Alarm
    0xA0 Temperature/Humidity over threshold alarm
    0xA1 Temperature/Humidity sensor abnormal alarm
    0xA2 Light sensor bright and dark changes
    0xA3 Shock alarm
    0xB0 Turn on the device
    0xB1 Turn off the device
    '''
    def set_alarm_type(self, data: bytes): 
        if len(data) != 1: 
            logging.error("Invalid alarm type data length")
            return 
        self.alarm_type = data.hex()
        str_alarm = check_alamr_type(data)
        logging.debug(f"Alarm type: {str_alarm}")
        
    '''
    1 bytes
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
    def set_terminal_info(self, data: bytes): 
        if len(data) != 1: 
            logging.error("Invalid terminal data length")
            return
        self.terminal = int.from_bytes(data)
        # print in binary format. remove 0b prefix
        str_type = bin(self.terminal)[2:] 
        logging.debug(f"terminal information: {str_type}")
    
    '''
    CSQ value , Hex code
    '''
    def set_gms_signal_strength(self, data: bytes): 
        if len(data) != 1: 
            logging.error("Invalid gms singal strngth data")
            return
        self.gms_signal_strength = int.from_bytes(data)
        logging.debug("GMS CSQ: {}".format(self.gms_signal_strength))
    
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
    def set_gsm_status(self, data: bytes): 
        if len(data) != 1: 
            logging.error("Invalid GSM status data length")
            return
        self.gsm_status = int.from_bytes(data)
        str_status = bin(self.gsm_status)[2:] 
        logging.debug(f"GSM status: {str_status}")
    
    '''
    2 bytes
    Unit:10mv, for example: 0175H=373(DEC), 375*10mV=3.73V
    '''
    def set_battery_voltage(self, data: bytes): 
        amount = int.from_bytes(data)
        self.battery_voltage = amount * 0.01
        logging.debug("battery voltage: {}V".format(self.battery_voltage))

    '''
    2 bytes
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
    def set_builtin_temperature(self, data: bytes): 
        self.builtin_temperature = None
        if len(data) !=2 : 
            logging.error("Invalid builtin temperature data length")
            return
        value = int.from_bytes(data)
        status = value >> 15
        sign = (value >>14)&0x01
        temp = (value & 0x3fff) * 0.1
        if status:
            logging.error("device builtin temperature sensor is abnormal")
            return
        if sign: 
            temp = -temp
        self.builtin_temperature = temp
        logging.debug(f"builtin temperature: {self.builtin_temperature}")

    '''
    2 bytes
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
    def set_builtin_humidity(self, data: bytes): 
        self.builtin_humidity = None
        if len(data) != 2: 
            logging.error("Invalid builtin humidity data length")
            return
        value = int.from_bytes(data)
        status = value >> 15
        humi = (value & 0x7fff) * 0.1
        if status:
            logging.error("device builtin humidity sensor is abnormal")
            return
        self.builtin_humidity = humi
        logging.debug(f"builtin humidity: {self.builtin_humidity}%")
    
    '''
    2 bytes
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
    def set_external_temperature(self, data: bytes): 
        self.external_temperature = None
        if len(data) !=2 : 
            logging.error("Invalid builtin temperature data length")
            return
        value = int.from_bytes(data)
        status = value >> 15
        sign = (value >>14)&0x01
        temp = (value & 0x3fff) * 0.1
        if status:
            logging.error("device external temperature sensor is abnormal")
            return
        if sign: 
            temp = -temp
        self.external_temperature = temp
        logging.debug(f"external temperature: {self.external_temperature}")
    
    '''
    2 bytes
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
    def set_external_humidity(self, data: bytes): 
        self.external_humidity = None
        if len(data) != 2: 
            logging.error("Invalid builtin humidity data length")
            return
        value = int.from_bytes(data)
        status = value >> 15
        humi = (value & 0x7fff) * 0.1
        if status:
            logging.error("device external sensor is abnormal")
            return
        self.external_humidity = humi
        logging.debug(f"external humidity: {self.external_humidity}%")

    '''
    2byte，unit：lux ,need convert to decimal
    '''
    def set_light_sensor_data(self, data: bytes): 
        self.light_sensor = None
        if len(data) != 2: 
            logging.error("Invalid light sensor data length")
            return
        self.light_sensor = int.from_bytes(data)
        logging.debug(f"Light: {self.light_sensor} lux")
    
    '''
     2byte，unit：mg, need convert to decimal
    '''
    def set_shock_sensor_data(self, data:bytes): 
        self.shock_sensor = None
        if len(data) != 2: 
            logging.error("Invalid shock sensor data length")
            return
        self.shock_sensor = int.from_bytes(data)
        logging.debug("Vibration: {} mg".format(self.shock_sensor))

    
    # clear all wifi information
    def reset_wifi_data(self): 
        self.wifi.clear()
        logging.debug("clear all wifi data")
        return
    
    '''
    add wifi data, since packet has multiple wifi data
    param: 
        @data_mac: 6 bytes， for example, 36 C2 E4 E2 6E 63 means the WIFI AP mac address is 36:C2:E4:E2:6E:63
        @data_rssi: 1 bytes. 1byte，need convert to decimal，unit：-dbm 
    '''
    def add_wifi(self, data_mac: bytes, data_rssi: bytes): 
        self.single_wifi_mac = None
        if len(data_mac) != 6 or len(data_rssi) != 1: 
            logging.error("Invalid single wifi AP mac data length")
            return
        address = data_mac.hex().upper()
        l = len(address)
        ll = []
        for i in range(0, l, 2): 
            ll.append(address[i:i+2])
        mac =  ":".join(ll)
        rssi = -int.from_bytes(data_rssi)
        wifi = WiFi(mac, rssi)
        self.wifi.append(wifi)
        logging.debug("Wifi Mac: [{}]".format(wifi))
    
    '''
    check stop bits of packet. 
    It should be "0x0D, 0x0A"
    '''
    def valid_packet_end(self, data: bytes): 
        if len(data) != 2: 
            logging.error("Invalid stop bits data length")
            return False
        ss = data.hex().upper()
        result = True if ss == '0D0A' else False
        return result

    '''
    analyze the packet data
    param:
         data: raw bytes array 
    return: True if success to parse all data
        False if error found
    '''
    def analyze_packet(self, data: bytes):
        pos = 0
        total_len = len(data)
        self.set_start_bites(data[0:2])
        '''
        The bytes length from the start at protocol number to the end at the CRC.
        '''
        self.set_packet_length(data[2:4])
        self.set_protocol_number(data[4:6])
        self.set_hardware_type(data[6:8])
        self.set_firmware_version(data[8:12])
        self.set_imei(data[12:20])
        self.set_rtc_time(data[20:26])
        gps_data_len = int.from_bytes(data[26:28])
        logging.debug("gps data length: {}".format(gps_data_len))
        status = data[28:29]
        self.set_utc_time(data[29:35])
        latitude = data[35:39]
        longitude = data[39:43]
        self.set_gps(status, latitude, longitude)
        self.set_direction(data[43:45])
        self.set_speed(data[45:47])
        self.set_lbs_data_len(data[47:49])
        self.set_lbs_number(data[49:50])
        self.set_lbs_signal(data[50:51])
        self.set_mobile_code(data[51:53])
        self.set_mobile_network_code(data[53:55])
        self.set_location_area_code(data[55:57])
        cell_id = data[57:61]
        rxRev = data[61:62]
        phy_cell_id = data[62:64]
        earfcn = data[64:67]        
        RSRP = data[67:68]
        RSRQ = data[68:69]
        RSSI = data[69:70]
        '''
        The status data length excluding “Status data length” itself. If this part is 0, there is no status data.
        # ERROR: protocol itself 2 bytes. but it is mismatched with real data, one byes should be compensated between longitude to status_data_len
        '''
        status_data_len = data[70:71] 
        self.set_alarm_type(data[71:72])
        self.set_terminal_info(data[72:73])
        self.set_gms_signal_strength(data[73:74])
        self.set_gsm_status(data[74:75])
        self.set_battery_voltage(data[75:77])
        self.set_builtin_temperature(data[77:79])
        self.set_builtin_humidity(data[79:81])
        # external temp/humidity data doesn't exist
        #external_temp = data[81:83]
        #external_humidity = data[83:85]
        self.set_light_sensor_data(data[81:83])
        self.set_shock_sensor_data(data[83:85])
        wifi_data_len = int.from_bytes(data[85:87])
        logging.debug("wifi_data_len:{}".format(wifi_data_len))
        pos = 87
        self.reset_wifi_data()
        if wifi_data_len > 0:
            # 7 bytes per wifi. 6 bytes is for mac address. 1 bytes for RSSI value
            for i in range(pos, pos+ wifi_data_len, 7):
                wifi_mac = data[i:i+6]
                wifi_rssi = data[i+6:i+7]
                self.add_wifi(wifi_mac, wifi_rssi)
            pos += wifi_data_len
        
        if pos + 6 != total_len: 
            logging.error("Packet length mismatched. Failed to anlayze all packet data")

        '''
        The value range of this part is between 1 and 9999
        '''
        self.packet_index =  int.from_bytes(data[-6:-4])
        
        '''
        The checked content is from the “protocol number” to the end at “CRC”, 
        including “protocol number”, excluding “CRC”.
        '''
        self.crc = data[-4:-2]
        result = self.valid_packet_end(data[-2:])
        return result