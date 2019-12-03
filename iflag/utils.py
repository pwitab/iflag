import datetime

from iflag import constants
from typing import Union


def crc16(data: Union[bytearray, bytes], initial_value=0x0000, byteorder="little"):
    """
    Calculates CRC 16
    Polynomial = X16 + X15 + X2 + 1. (X15 + X2 + 1) = 0x8005
    """
    polynomial = 0x8005
    crc = initial_value
    for b in data:
        crc ^= b << 8
        for _ in range(0, 8):
            if crc & 0b1000000000000000:
                crc = (crc << 1) ^ polynomial
            else:
                crc = crc << 1
    crc &= 0xFFFF  # ensure 16 bits

    result = crc.to_bytes(2, byteorder)

    return result


def add_crc(data: bytes):
    """
    Will calculate a crc and add it to the input data
    """
    crc = crc16(data)
    return data + crc


def crc_valid(data: bytes, crc: bytes):
    computed_crc = crc16(data)
    return crc == computed_crc


def date_to_byte(date: datetime.datetime):
    day_index = 17
    day = date.day
    day_value = day << day_index
    month_index = 22
    month = date.month
    month_value = month << month_index
    year_index = 26
    year = date.year - 2000  # we need to remove 2000. Program will work for 1000 years.
    year_value = year << year_index
    hour_index = 12
    hour = date.hour
    hour_value = hour << hour_index
    minute_index = 6
    minute = date.minute
    minute_value = minute << minute_index
    second_index = 0
    second = date.second
    second_value = second << second_index

    total_value = (
        second_value + minute_value + hour_value + day_value + month_value + year_value
    )
    out_bytes = total_value.to_bytes(4, "big")
    return out_bytes


def byte_to_date(in_bytes: bytes):
    # TODO: UTC offset!
    in_value = int.from_bytes(in_bytes, "big")
    day_bitmask = 0b00000000001111100000000000000000
    month_bitmask = 0b00000011110000000000000000000000
    year_bitmask = 0b11111100000000000000000000000000
    hour_bitmask = 0b00000000000000011111000000000000
    minute_bitmask = 0b00000000000000000000111111000000
    second_bitmask = 0b00000000000000000000000000111111
    day_index = 17
    month_index = 22
    year_index = 26
    hour_index = 12
    minute_index = 6
    second_index = 0

    day_value = (in_value & day_bitmask) >> day_index
    month_value = (in_value & month_bitmask) >> month_index
    year_value = ((in_value & year_bitmask) >> year_index) + 2000
    hour_value = (in_value & hour_bitmask) >> hour_index
    minute_value = (in_value & minute_bitmask) >> minute_index
    second_value = (in_value & second_bitmask) >> second_index

    dt = datetime.datetime(
        year=year_value,
        month=month_value,
        day=day_value,
        hour=hour_value,
        minute=minute_value,
        second=second_value,
    )

    return dt
