"""Build TZ binary data packets matching TZPacket.ts / server.ts layout."""

from datetime import datetime, timezone
from typing import Optional

from utils.crc16 import crc16

# Default LBS block from a real TT19 sample (20 bytes after length field).
_DEFAULT_LBS = bytes.fromhex("01d2044000203034020a1a5c0022000ea66d0855")


def encode_imei(serial: str) -> bytes:
    """Encode 15-digit serial into 8-byte IMEI field (leading nibble ignored on parse)."""
    digits = "".join(ch for ch in str(serial) if ch.isdigit())
    if len(digits) < 15:
        digits = digits.zfill(15)
    elif len(digits) > 15:
        digits = digits[-15:]
    hex_str = ("0" + digits)[:16]
    return bytes.fromhex(hex_str)


def encode_datetime(dt: datetime) -> bytes:
    """Encode UTC datetime as 6 bytes: year-2000, month, day, hour, minute, second."""
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return bytes(
        [
            dt.year - 2000,
            dt.month,
            dt.day,
            dt.hour,
            dt.minute,
            dt.second,
        ]
    )


def encode_temperature(temp_c: float, abnormal: bool = False) -> bytes:
    """2 bytes: bit15 abnormal, bit14 sign, bits0-13 value*10."""
    if abs(temp_c) > 1638.3:
        raise ValueError(f"temperature out of range: {temp_c}")
    sign = 1 if temp_c < 0 else 0
    raw = int(round(abs(temp_c) * 10)) & 0x3FFF
    value = ((1 << 15) if abnormal else 0) | (sign << 14) | raw
    return value.to_bytes(2, byteorder="big", signed=False)


def encode_humidity(humidity: float, abnormal: bool = False) -> bytes:
    """2 bytes: bit15 abnormal, bits0-14 RH*10."""
    if humidity < 0 or humidity > 1000:
        raise ValueError(f"humidity out of range: {humidity}")
    raw = int(round(humidity * 10)) & 0x7FFF
    value = ((1 << 15) if abnormal else 0) | raw
    return value.to_bytes(2, byteorder="big", signed=False)


def encode_battery_percent(percent: float) -> bytes:
    """2 bytes battery field as used by the server (percent value)."""
    value = max(0, min(100, int(round(percent))))
    return value.to_bytes(2, byteorder="big", signed=False)


def build_data_packet(
    serial: str,
    temperature: float,
    humidity: float,
    battery: float,
    dt: Optional[datetime] = None,
    packet_index: int = 1,
    hardware: bytes = b"\x04\x0d",
    firmware: bytes = b"\x02\x06\x00\x00",
    csq: int = 20,
    light: int = 50,
    shock: int = 0,
    lbs_data: bytes = _DEFAULT_LBS,
) -> bytes:
    """
    Build a full TZ interval GPRS data packet (protocol $$).

    Layout (no GPS, with LBS, status length 16, no WiFi):
      TZ | len | $$ | hw | fw | imei | rtc | gps_len=0 | lbs | status | wifi_len=0 | idx | crc | 0d0a
    """
    if dt is None:
        dt = datetime.utcnow()

    packet_index = ((packet_index - 1) % 9999) + 1

    body = bytearray()
    body.extend(b"$$")
    body.extend(hardware)
    body.extend(firmware)
    body.extend(encode_imei(serial))
    body.extend(encode_datetime(dt))
    body.extend((0).to_bytes(2, "big"))  # GPS length
    body.extend(len(lbs_data).to_bytes(2, "big"))
    body.extend(lbs_data)

    # status length 16: alarm..humi + ext_temp + light + shock
    status = bytearray()
    status.append(0xAA)  # Interval GPRS data
    status.append(0x00)  # terminal info (normal)
    status.append(csq & 0xFF)
    status.append(0x3F)  # GSM status: module up, SIM, registered, GPRS, internet
    status.extend(encode_battery_percent(battery))
    status.extend(encode_temperature(temperature))
    status.extend(encode_humidity(humidity))
    status.extend(encode_temperature(temperature))  # external probe mirrors builtin
    status.extend(light.to_bytes(2, "big"))
    status.extend(shock.to_bytes(2, "big"))
    assert len(status) == 16

    body.extend(len(status).to_bytes(2, "big"))
    body.extend(status)
    body.extend((0).to_bytes(2, "big"))  # WiFi length
    body.extend(packet_index.to_bytes(2, "big"))

    crc = crc16(bytes(body))
    body.extend(crc.to_bytes(2, "big"))

    # packet_len = bytes from protocol number through CRC (inclusive)
    packet_len = len(body)
    packet = bytearray()
    packet.extend(b"TZ")
    packet.extend(packet_len.to_bytes(2, "big"))
    packet.extend(body)
    packet.extend(b"\x0d\x0a")
    return bytes(packet)
