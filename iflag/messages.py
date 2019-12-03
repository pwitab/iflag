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


class ReadDatabaseMessage(CorusMessage):
    def __init__(self, database="interval", start=None, stop=None):
        self.database = database
        self.start = start
        self.stop = stop
        self.session_persistence = False  # otherwise it will resend last failure.
        self.count_records = (
            False
        )  # otherwise we would get number of records in first frame
        self.options_bitmask = b"\xFF\xFF\xFF\xF9"  # all values!
        self.db_id_map = {
            "interval": 0,
            "hourly": 1,
            "daily": 2,
            "monthly": 3,
            "event": 4,
            "parameter": 5,
        }

    @property
    def db_byte(self) -> bytes:
        b = b''
        b &= self.db_id_map[self.database]
        if self.session_persistence:
            b &= 0b10000000

        if self.count_records:
            b &= 0b00010000

        return b




