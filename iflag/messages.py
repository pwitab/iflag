import abc
import attr

from iflag import utils
from typing import List


class CorusMessageABC(abc.ABC):
    """
    Base class for corus messages.
    """

    @abc.abstractmethod
    def to_bytes(self):
        """
        Converts the message to bytes
        """
        raise NotImplementedError("Needs to be implemented in subclass")


class ReadRequest(CorusMessageABC):
    """
    Class to structure a read request to the device.
    """

    def __init__(self, parameter_ids: List[int]):
        self.parameter_ids = parameter_ids

    def to_bytes(self):
        id_bytes = b""
        for parameter_id in self.parameter_ids:
            if parameter_id < 239:
                id_bytes += parameter_id.to_bytes(1, "big")
            else:
                id_bytes += (parameter_id | 0b1111000000000000).to_bytes(2, "big")

        size = len(id_bytes).to_bytes(1, "big")
        message = b"\x01\xbf" + size + id_bytes + b"\x03"
        out_data = utils.add_crc(message)
        return out_data

    def __repr__(self):
        return f"{self.__class__.__name__}(parameter_ids={self.parameter_ids!r}"


@attr.s(auto_attribs=True)
class WriteData:
    """Simple dataclass for managing write data"""

    id: int
    data: bytes

    def to_bytes(self) -> bytes:
        if self.id < 239:  # can be expressed in single byte
            return self.id.to_bytes(1, "big") + self.data
        else:  # fill the highest bits with 1:s when representing as 2 bytes
            return (self.id | 0b1111000000000000).to_bytes(2, "big")


class WriteRequest(CorusMessageABC):
    """
    Class to structure a write request to the device.
    """

    def __init__(self, data: List[WriteData]):
        self.data = data

    def to_bytes(self) -> bytes:
        data_bytes = b"".join([item.to_bytes() for item in self.data])

        size = len(data_bytes).to_bytes(1, "little")
        message = b"\x01\xff" + size + data_bytes + b"\x03"
        out_data = utils.add_crc(message)
        return out_data

    def __repr__(self):
        return f"{self.__class__.__name__}(data={self.data!r}"


class ReadDatabaseRequest(CorusMessageABC):
    """
    Class to structure a read database request to device.
    The session persistence feature has been turned off to make a more predictable
    client implementation.
    The "count records" feature has been turned off since it is not used.
    The request will always request all data available in the database.

    :param database: The database to read.
    :param start: The date for the newest values to request
    :param stop: The date for the oldest value to request
    """

    db_id_map = {
        "interval": 0,
        "hourly": 1,
        "daily": 2,
        "monthly": 3,
        "event": 4,
        "parameter": 5,
    }

    def __init__(self, database="interval", start=None, stop=None):
        self.database = database
        self.start = start
        self.stop = stop
        self.session_persistence = False  # otherwise it will resend last failure.
        self.count_records = (
            False
        )  # otherwise we would get number of records in first frame
        self.options_bitmask = b"\xF9\xFF\xFF\xFF"  # all values!

    @property
    def db_byte(self) -> bytes:
        """
        Encodes the byte that indicates which db to read.
        :return:
        """

        b = self.db_id_map[self.database]
        if self.session_persistence:
            b &= 0b10000000

        if self.count_records:
            b &= 0b00010000

        return b.to_bytes(1, "big")

    def to_bytes(self):
        data = (
            b"\x01\xbe\x0d"
            + self.db_byte
            + self.options_bitmask
            + utils.date_to_byte(self.start)
            + utils.date_to_byte(self.stop)
            + b"\x03"
        )
        out_data = utils.add_crc(data)
        return out_data

    def __repr__(self):
        return (
            f"{self.__class__.__name__}("
            f"database={self.database!r}, "
            f"start={self.start!r}, "
            f"stop={self.stop!r}"
            f")"
        )
