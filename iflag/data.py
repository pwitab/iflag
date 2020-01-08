import datetime
import decimal
import struct
from iflag import utils, exceptions
import typing
import attr


class CorusData:
    byte_order = "little"
    length = 1
    value_type = int

    @classmethod
    def check_in_data(cls, in_data):
        if len(in_data) != cls.length:
            raise ValueError(
                f"{cls.__class__.__name__} can only be of length {cls.length}, "
                f"received data {in_data!r} of length {len(in_data)}"
            )

    def check_value_type(self, value):
        if not isinstance(value, self.value_type):
            raise exceptions.DataError(
                f"Class {self.__class__.__name__} need a value of "
                f"type {self.value_type}"
            )

    @classmethod
    def from_bytes(cls, in_bytes: bytes):
        raise NotImplementedError("from_bytes must be implemented in subclass")

    def to_bytes(self):
        raise NotImplementedError("to_bytes must be implemented in subclass")


class Date(CorusData):
    length = 4
    value_type = datetime.datetime

    def __init__(self, value: datetime.datetime):
        self.check_value_type(value)
        self.value = value

    @classmethod
    def from_bytes(cls, in_bytes: bytes):
        cls.check_in_data(in_bytes)
        date = utils.byte_to_date(in_bytes)
        return cls(value=date)

    def to_bytes(self):
        return utils.date_to_byte(self.value)


class Integer(CorusData):
    """
    Base for integers.
    """

    length = 1
    value_type = int

    def __init__(self, value: int):
        self.check_value_type(value)
        self.value = value

    @classmethod
    def from_bytes(cls, in_bytes: bytes):
        cls.check_in_data(in_bytes)
        return cls(value=int.from_bytes(in_bytes, cls.byte_order))

    def to_bytes(self):
        return self.value.to_bytes(int(self.length), self.byte_order)


class Byte(Integer):
    """
    8 bit unsigned integer. mimic of base class
    """

    pass


class EWord(Integer):
    """
    24 bit unsigned integer
    """

    length = 3


class Word(Integer):
    """
    16 bit integer
    """

    length = 2


class ULong(Integer):
    """
    32 bit integer
    """

    length = 4


class EULong(Integer):
    """
    40 bit integer
    """

    length = 5


class Float(CorusData):
    """
    32 bit float
    """

    length = 4
    value_type = decimal.Decimal

    def __init__(self, value: decimal.Decimal):
        self.check_value_type(value)
        self.value = value

    @classmethod
    def from_bytes(cls, in_bytes: bytes):
        cls.check_in_data(in_bytes)
        dec = decimal.Decimal(str(struct.unpack("<f", in_bytes)[0]))
        # On a 64bit system you will get problem with extra "garbage" bits/decimals in
        # conversion from 32 bits to 64 bit.
        # So we quantize the resulting decimal to get rid of the excess.
        return cls(dec.quantize(decimal.Decimal("0.000001")))

    def to_bytes(self):
        return struct.pack("<f", float(self.value))


class Float1(CorusData):
    """
    16 bit signed integer with multiplier coefficient of 100.
    Only used for temperatures in the database.
    Ex. -1612 0 -16.12 degrees (C or F)
    """

    length = 2
    value_type = decimal.Decimal

    def __init__(self, value: decimal.Decimal):
        self.check_value_type(value)
        self.value = value

    @classmethod
    def from_bytes(cls, in_bytes: bytes):
        cls.check_in_data(in_bytes)
        val = (
            decimal.Decimal(int.from_bytes(in_bytes, cls.byte_order, signed=True)) / 100
        )
        return cls(value=val)

    def to_bytes(self):
        raise NotImplementedError(
            "No need to make bytes of Float1 values since they "
            "are only available to read in database"
        )


class Float2(CorusData):
    """
    16 bit structure containing value and exponent.
    bit 0-14 = number, bit 15 = exponent
    number * 10 ^ (exponent - 3)
    Only used for pressure in database.
    """

    length = 2
    value_type = decimal.Decimal

    def __init__(self, value: decimal.Decimal):
        self.check_value_type(value)
        self.value = value

    @classmethod
    def from_bytes(cls, in_bytes: bytes):
        cls.check_in_data(in_bytes)
        val = int.from_bytes(in_bytes, cls.byte_order)
        num = val & 0b0111111111111111
        exp = ((val & 0b1000000000000000) >> 15) - 3
        dec_input = decimal.Decimal(f"{num}e{exp}")
        return cls(value=dec_input)

    def to_bytes(self):
        raise NotImplementedError(
            "No need to make bytes of Float2 values since they "
            "are only available to read in database"
        )


class Float3(CorusData):
    """
    16 bit structure containing value and exponent.
    bit 0-13 = number, bit 14-15 = exponent
    number * 10 ^ (exponent - 2)
    Only used for pressure in database.
    """

    length = 2
    value_type = decimal.Decimal

    def __init__(self, value: decimal.Decimal):
        self.check_value_type(value)
        self.value = value

    @classmethod
    def from_bytes(cls, in_bytes: bytes):
        cls.check_in_data(in_bytes)
        val = int.from_bytes(in_bytes, cls.byte_order)
        num = val & 0b0011111111111111
        exp = ((val & 0b1100000000000000) >> 14) - 2
        dec_input = decimal.Decimal(f"{num}e{exp}")
        return cls(value=dec_input)

    def to_bytes(self):
        raise NotImplementedError(
            "No need to make bytes of Float3 values since they "
            "are only available to read in database"
        )


class Index(CorusData):
    # TODO: Validate that correct bytes are used.
    """
    Index consists of 8 bytes, 4 bytes is the integer-part and 4 is the decimal part.
    The decimal part needs to be divided by the decimal factor of 100000000
    """
    length = 8
    value_type = decimal.Decimal

    def __init__(self, value: decimal.Decimal):
        self.check_value_type(value)
        self.value = value

    @classmethod
    def from_bytes(cls, in_bytes: bytes):
        cls.check_in_data(in_bytes)
        num_bytes = in_bytes[:4]
        dec_bytes = in_bytes[4:]
        dec = decimal.Decimal(
            int.from_bytes(dec_bytes, cls.byte_order)
        ) / decimal.Decimal(100000000)
        num = decimal.Decimal(int.from_bytes(num_bytes, cls.byte_order))
        return cls(value=(num + dec).quantize(decimal.Decimal("0.001")))

    def to_bytes(self):
        raise NotImplementedError(
            "No need to make bytes of Index values since they "
            "are only available to read in database"
        )


class Null2(CorusData):
    length = 2

    def __init__(self, value=None):
        self.value = None

    @classmethod
    def from_bytes(cls, in_bytes: bytes):
        return cls(None)

    def to_bytes(self):
        return b"\x00\x00"


class Null4(CorusData):
    length = 4

    def __init__(self, value=None):
        self.value = None

    @classmethod
    def from_bytes(cls, in_bytes: bytes):
        return cls(None)

    def to_bytes(self):
        return b"\x00\x00\x00\x00"


class CorusString(CorusData):
    length = 8
    value_type = str

    def __init__(self, value: str):
        self.check_value_type(value)
        self.value = value

    @classmethod
    def from_bytes(cls, in_bytes: bytes):
        cls.check_in_data(in_bytes)
        return cls(in_bytes.decode("latin-1"))

    def to_bytes(self):
        return self.value.encode("latin-1")


@attr.s(auto_attribs=True)
class ParameterSpecification:
    name: str
    id: int
    description: str
    read: bool
    write: bool
    data_class: typing.Type[CorusData]


PARAMETERS: typing.List[ParameterSpecification] = [
    ParameterSpecification(
        name="firmware_version",
        id=0,
        description="Main firmware version",
        read=True,
        write=False,
        data_class=CorusString,
    ),
    ParameterSpecification(
        name="pulse_weight",
        id=1,
        description="Input pulse weight",
        read=True,
        write=True,
        data_class=Float,
    ),
    ParameterSpecification(
        name="compressibility_formula",
        id=15,
        description=(
            "Compressibility Formula: 0=AGANX19 Standard, 1=S-GERG88, 2=PT, "
            "3=AGANx19 Modified, 4=Not Used, 5=T, 6=16 Coeff. 7=AGA8"
        ),
        read=True,
        write=True,
        data_class=Byte,
    ),
    ParameterSpecification(
        name="pressure_base",
        id=19,
        description="Base pressure, in selected pressure unit",
        read=True,
        write=True,
        data_class=Float,
    ),
    ParameterSpecification(
        name="temperature_base",
        id=24,
        description="Base temperature, in Kelvin",
        read=True,
        write=True,
        data_class=Float,
    ),
    ParameterSpecification(
        name="pressure_low",
        id=30,
        description="Low pressure threshold (Pmin)",
        read=True,
        write=True,
        data_class=Float,
    ),
    ParameterSpecification(
        name="pressure_high",
        id=31,
        description="High pressure threshold (Pmax)",
        read=True,
        write=True,
        data_class=Float,
    ),
    ParameterSpecification(
        name="temperature_low",
        id=40,
        description="Low temperature threshold (Tmin)",
        read=True,
        write=True,
        data_class=Float,
    ),
    ParameterSpecification(
        name="temperature_high",
        id=41,
        description="High temperature threshold (Tmax)",
        read=True,
        write=True,
        data_class=Float,
    ),
    ParameterSpecification(
        name="datetime",
        id=106,
        description="Current time and date",
        read=True,
        write=True,
        data_class=Date,
    ),
    ParameterSpecification(
        name="battery_days",
        id=107,
        description="Battery Autonomy Counter, in days",
        read=True,
        write=True,
        data_class=Word,
    ),
    ParameterSpecification(
        name="index_unconverted",
        id=148,
        description="Unconverted Index",
        read=True,
        write=True,
        data_class=Index,
    ),
    ParameterSpecification(
        name="index_converted",
        id=149,
        description="Converted Index",
        read=True,
        write=True,
        data_class=Index,
    ),
]

PARAMETERS_BY_NAME: typing.Mapping[str, ParameterSpecification] = {
    parameter.name: parameter for parameter in PARAMETERS
}
PARAMETERS_BY_ID: typing.Mapping[int, ParameterSpecification] = {
    parameter.id: parameter for parameter in PARAMETERS
}
