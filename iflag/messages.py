from iflag import utils
from typing import List

class CorusMessage:
    ENCODING = "latin-1"
    """
    Base class for iflag/corus messages.
    """

    def to_representation(self):
        raise NotImplementedError("Needs to be implemented in subclass")

    def to_bytes(self):
        """
        Ensures the correct encoding to bytes.
        """
        return self.to_representation().encode(self.ENCODING)

    @classmethod
    def from_representation(cls, string_data):
        raise NotImplementedError("Needs to be implemented in subclass")

    @classmethod
    def from_bytes(cls, bytes_data):
        """
        Ensures the correct decoding from  bytes.
        """

        return cls.from_representation(bytes_data.decode(cls.ENCODING))

class ReadRequest(CorusMessage):
    def __init__(self, parameter_ids: List[int]):
        self.parameter_ids = parameter_ids

    def to_bytes(self):
        id_bytes = b''
        for parameter_id in self.parameter_ids:
            id_bytes += parameter_id.to_bytes(1, 'little')

        size = len(self.parameter_ids).to_bytes(1, 'little')
        message = (b'\x01\xbf' + size + id_bytes + b'\x03')
        out_data = utils.add_crc(message)
        return out_data



class ReadDatabaseRequest(CorusMessage):
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
