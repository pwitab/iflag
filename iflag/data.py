from datetime import datetime
from decimal import Decimal
import struct
from functools import reduce

from iflag import utils, exceptions
from typing import Optional, Type, Any, Union
import attr
import abc


def float_to_decimal(_float: Union[int, float]) -> Decimal:
    """
    On a 64bit system you will get problem with extra "garbage" bits/decimals in
    conversion from 32 bits to 64 bit.
    So we quantize the resulting decimal to fixed precision to get rid of the excess.
    And to not have tons of extra precision we also normalize the value.
    :param _float: float or int to convert to Decimal
    :return:
    """
    return Decimal().from_float(_float).quantize(Decimal("0.000001")).normalize()


class CorusDataABC(abc.ABC):
    BYTE_ORDER: str = "little"
    LENGTH: int = 1
    VALUE_TYPE: Type = int

    def __init__(self, value: Optional[Any]):
        self.check_value_type(value)
        self.value = value

    @classmethod
    def check_in_data(cls, in_data):
        if len(in_data) != cls.LENGTH:
            raise ValueError(
                f"{cls.__class__.__name__} can only be of length {cls.LENGTH}, "
                f"received data {in_data!r} of length {len(in_data)}"
            )

    @classmethod
    def is_none_data(cls, in_data: bytes) -> bool:
        """
        When data is returned as none data all the length is "ones" (ex. 0xffff)
        :param in_data:
        :return:
        """
        return in_data == (b"\xff" * cls.LENGTH)

    def check_value_type(self, value):
        if value is None:
            return
        if not isinstance(value, self.VALUE_TYPE):
            raise exceptions.DataError(
                f"Class {self.__class__.__name__} need a value of "
                f"type {self.VALUE_TYPE}"
            )

    @classmethod
    @abc.abstractmethod
    def to_python(cls, in_bytes: bytes):
        raise NotImplementedError("to_python must be implemented in subclass")

    @abc.abstractmethod
    def from_python(self, value: Any):
        raise NotImplementedError("from_python must be implemented in subclass")

    @classmethod
    def from_bytes(cls, in_bytes: bytes):
        cls.check_in_data(in_bytes)
        if cls.is_none_data(in_bytes):
            return cls(value=None)
        return cls(value=cls.to_python(in_bytes))

    def to_bytes(self):
        if self.value is None:
            return b"\xff" * self.LENGTH
        else:
            return self.from_python(self.value)


class Date(CorusDataABC):
    LENGTH = 4
    VALUE_TYPE = datetime

    @classmethod
    def to_python(cls, in_bytes: bytes):
        return utils.byte_to_date(in_bytes)

    def from_python(self, value: datetime):
        return utils.date_to_byte(value)


class Byte(CorusDataABC):
    """
    8 bit unsigned integer. mimic of base class
    """

    LENGTH = 1
    VALUE_TYPE = int

    @classmethod
    def to_python(cls, in_bytes: bytes):
        return struct.unpack("<B", in_bytes)[0]

    def from_python(self, value: int):
        return struct.pack("<B", value)


class EWord(CorusDataABC):
    """
    24 bit unsigned integer
    """

    LENGTH = 3
    VALUE_TYPE = Decimal

    @classmethod
    def to_python(cls, in_bytes: bytes):
        in_bytes = in_bytes + b"\x00"  # padding 1 bytes so it is possible to use struct
        return float_to_decimal(struct.unpack("<I", in_bytes)[0])

    def from_python(self, value: Decimal):
        return struct.pack("<I", int(value))[:-1]  # removed last unused byte.


class Word(CorusDataABC):
    """
    16 bit unsigned integer
    """

    LENGTH = 2
    VALUE_TYPE = Decimal

    @classmethod
    def to_python(cls, in_bytes: bytes):
        return float_to_decimal(struct.unpack("<H", in_bytes)[0])

    def from_python(self, value: Decimal):
        return struct.pack("<H", int(value))


class ULong(CorusDataABC):
    """
    32 bit unsigned integer
    """

    LENGTH = 4
    VALUE_TYPE = Decimal

    @classmethod
    def to_python(cls, in_bytes: bytes):
        return float_to_decimal(struct.unpack("<I", in_bytes)[0])

    def from_python(self, value: Decimal):
        return struct.pack("<I", int(value))


class EULong(CorusDataABC):
    """
    40 bit unsigned integer
    """

    LENGTH = 5
    VALUE_TYPE = Decimal

    @classmethod
    def to_python(cls, in_bytes: bytes):
        in_bytes = in_bytes + b"\x00\x00\x00"  # pad with 3 bytes to use struct
        return float_to_decimal(struct.unpack("<Q", in_bytes)[0])

    def from_python(self, value: Decimal):
        return struct.pack("<Q", int(value))[:-3]


class Float(CorusDataABC):
    """
    32 bit float
    """

    LENGTH = 4
    VALUE_TYPE = Decimal

    @classmethod
    def to_python(cls, in_bytes: bytes):
        return float_to_decimal(struct.unpack("<f", in_bytes)[0])

    def from_python(self, value: Decimal):
        return struct.pack("<f", float(value))


class Float1(CorusDataABC):
    """
    16 bit signed integer with multiplier coefficient of 100.
    Only used for temperatures in the database.
    Ex. -1612 0 -16.12 degrees (C or F)
    """

    LENGTH = 2
    VALUE_TYPE = Decimal

    @classmethod
    def to_python(cls, in_bytes: bytes):

        return float_to_decimal(struct.unpack("<h", in_bytes)[0]) / Decimal("100")

    def from_python(self, value: Decimal):
        return struct.pack("<h", int(value))


class Float2(CorusDataABC):
    """
    16 bit structure containing value and exponent.
    bit 0-14 = number, bit 15 = exponent
    number * 10 ^ (exponent - 3)
    Only used for pressure in database.
    """

    LENGTH = 2
    VALUE_TYPE = Decimal

    @classmethod
    def to_python(cls, in_bytes: bytes):
        val = struct.unpack("<H", in_bytes)[0]
        num = val & 0b0111111111111111
        exp = ((val & 0b1000000000000000) >> 15) - 3
        return Decimal(f"{num}e{exp}")

    def from_python(self, value: Decimal):
        # TODO: Tons of edge cases.
        sign, digits, exponent = value.as_tuple()
        if -3 > exponent > -2:
            raise ValueError("Exponent part can only be -3 or -2")
        integer = reduce(lambda rst, x: rst * 10 + x, digits)
        encoded_exponent = (exponent + 3) << 15

        return struct.pack("<H", (integer + encoded_exponent))


class Float3(CorusDataABC):
    """
    16 bit structure containing value and exponent.
    bit 0-13 = number, bit 14-15 = exponent
    number * 10 ^ (exponent - 2)
    Only used for pressure in database.
    """

    LENGTH = 2
    VALUE_TYPE = Decimal

    @classmethod
    def to_python(cls, in_bytes: bytes):
        val = struct.unpack("<H", in_bytes)[0]
        num = val & 0b0011111111111111
        exp = ((val & 0b1100000000000000) >> 14) - 1
        return Decimal(f"{num}e{exp}")

    def from_python(self, value: Decimal):
        # TODO: Tons of edge cases
        sign, digits, exponent = value.as_tuple()
        if -1 > exponent > 2:
            raise ValueError("Exponent part can only be -1 to 2")
        integer = reduce(lambda rst, x: rst * 10 + x, digits)
        encoded_exponent = (exponent + 1) << 14

        return struct.pack("<H", (integer + encoded_exponent))


class Index(CorusDataABC):
    """
    Index consists of 8 bytes, 4 bytes is the integer-part and 4 is the decimal part.
    The decimal part needs to be divided by the decimal factor of 100000000
    """

    LENGTH = 8
    VALUE_TYPE = Decimal

    @classmethod
    def to_python(cls, in_bytes: bytes):
        integer, fraction = struct.unpack("<II", in_bytes)
        return (
            Decimal(integer) + (Decimal(fraction) / Decimal("100000000"))
        ).normalize()

    def from_python(self, value: Any):
        raise NotImplementedError(
            "No need to make bytes of Index values since they "
            "are only available to read in database"
        )


class Index9(CorusDataABC):
    """
    Index9 consists of 9 bytes, 5 bytes is the integer-part and 4 is the decimal part.
    The decimal part needs to be divided by the decimal factor of 100000000
    """

    LENGTH = 9
    VALUE_TYPE = Decimal

    @classmethod
    def to_python(cls, in_bytes: bytes):
        integer_bytes = in_bytes[:5] + b"\x00\x00\x00"  # pad so we can use struct.
        fraction_bytes = in_bytes[5:]
        integer = struct.unpack("<Q", integer_bytes)[0]
        fraction = struct.unpack("<I", fraction_bytes)[0]

        return (
            Decimal(integer) + (Decimal(fraction) / Decimal("100000000"))
        ).normalize()

    def from_python(self, value: Any):
        raise NotImplementedError(
            "No need to make bytes of Index values since they "
            "are only available to read in database"
        )


class Null2(CorusDataABC):
    LENGTH = 2

    @classmethod
    def to_python(cls, in_bytes: bytes):
        return None

    def from_python(self, value: Any):
        return b"\x00\x00"


class Null4(CorusDataABC):
    LENGTH = 4

    @classmethod
    def to_python(cls, in_bytes: bytes):
        return None

    def from_python(self, value: Any):
        return b"\x00\x00\x00\x00"


class CorusString(CorusDataABC):
    LENGTH = 8
    VALUE_TYPE = str

    @classmethod
    def to_python(cls, in_bytes: bytes):
        return in_bytes.rstrip(b"\x00").decode("latin-1")

    def from_python(self, value: str):
        out_bytes = value.encode("latin-1")
        if len(out_bytes) > 8:
            return out_bytes[:8]
        if len(out_bytes) < 8:
            return out_bytes + b"\x00" * (8 - len(out_bytes))
        else:
            return out_bytes


@attr.s(auto_attribs=True)
class DatabaseRecordParameter:
    """
    Represents how to interpret a database values. A sequence of `DatabaseRecordParameters`
    can be used to parse a database record.
    """

    name: str
    data_class: Type[CorusDataABC]
    affected_by_pulse_input: bool = attr.ib(default=False)
    multiplied: Optional[Decimal] = attr.ib(default=None)


@attr.s(auto_attribs=True)
class IFlagParameter:
    """
    Represents a parameter in IFlag. Different firmwares can have different values on
    different positions and in different formats. This provides an interface to the
    structure of the IFlag message but the user needs to know the correct position and
    format of the data that is read or written.
    """

    id: int
    data_class: Type[CorusDataABC]
