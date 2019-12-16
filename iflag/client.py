import logging

from iflag.parse import ParseConfigItem
from iflag.transport import TcpTransport, BaseTransport
from iflag.messages import ReadDatabaseRequest, ReadRequest
from typing import Tuple, Optional, List
from iflag import parse, utils
from iflag.data import PARAMETERS, PARAMETERS_BY_NAME

logger = logging.getLogger(__name__)


class CorusClient:
    def __init__(self, transport: BaseTransport, password: str = "00000000"):
        self.transport = transport
        self.password = password

    @classmethod
    def with_tcp_transport(cls, address: Tuple[str, int], password: str = "00000000"):
        trans = TcpTransport(address)
        return cls(transport=trans, password=password)

    def connect(self):
        """
        Connect to the device
        """
        self.transport.connect()

    def disconnect(self):
        """
        Disconnect from the device
        """
        self.transport.disconnect()

    def wakeup(self):
        """
        Simmilar to IEC62056-21 it is needed to send a sequence of null bytes to the
        device for it to wake up the interface. Protocol docs says at least 12 bytes but
        other software uses 200 bytes. We will stick to 200 bytes to not get any issues.
        The device should return 3 null bytes when it is ready.
        """
        wakeup_data = bytes(200)
        self.transport.send(wakeup_data)
        response = self.transport.recv(3)
        if response != b"\x00\x00\x00":
            raise Exception("Received non null wakeup response")

    def sign_on(self):
        """
        Similar sign on as IEC 62056-21. But no need to send a meter address. Device
        returns identification that has no special meaning. At least not over TCP.
        Then a standard Ack is sent.
        Then a "Password" exchange is done, but not really, just send the code PASS back
        and forth. So we just fast forward all of this to get to the correct state.
        """

        sign_on_message = b"/?!\r\n"
        self.transport.send(sign_on_message)
        ident = self.transport.simple_read(start_char="/", end_char="\x0a")
        ack_message = b"\x06\x30\x37\x30\x0d\x0a"
        self.transport.send(ack_message)
        pass_msg = self.transport.recv(6)
        # TODO: check the crc
        self.transport.send(pass_msg)
        ack = self.transport.recv(1)
        if ack != b"\x06":
            raise Exception("Ack not refeived after signon")

    def read_parameters_by_name(self, parameter_names: List[str]) -> dict:
        # verify valid parameters:
        if not all(
            [(parameter in PARAMETERS_BY_NAME.keys()) for parameter in parameter_names]
        ):
            raise ValueError(f"parameter_names contains not known parameter name")

        parameter_ids = [
            PARAMETERS_BY_NAME[parameter].id for parameter in parameter_names
        ]
        parse_config = [
            ParseConfigItem(
                name=PARAMETERS_BY_NAME[parameter].name,
                data_class=PARAMETERS_BY_NAME[parameter].data_class,
            )
            for parameter in parameter_names
        ]
        parser = parse.CorusDataParser(parsing_config=parse_config)
        in_data = self.read_parameters_by_id(parameter_ids)
        data = parser.parse(in_data)
        return data

    def read_parameters_by_id(self, parameters_ids: List[int]) -> bytes:
        msg = ReadRequest(parameters_ids).to_bytes()
        self.transport.send(msg)

        read_data = self._read_response()

        return read_data

    def _read_response(self) -> bytes:
        in_bytes = b""

        first_char = self.transport.recv(1)
        if not first_char == b"\x01":
            raise Exception("first char is not SOH")

        length_byte = self.transport.recv(1)
        data_length = int.from_bytes(bytes=length_byte, byteorder="big")

        data = self.transport.recv(data_length)

        end_char = self.transport.recv(1)
        if not end_char == b"\x03":
            raise Exception("end char not ETX")

        in_bytes += first_char + length_byte + data + end_char

        crc = self.transport.recv(2)

        total_data = in_bytes + crc
        logger.debug(f"Total Data: {total_data!r}")

        if not utils.crc_valid(in_bytes, crc):
            # Send nack if crc is not valid
            logger.debug(
                f"Message failed CRC validation. Message: {in_bytes!r}, "
                f"received_crc: {crc!r}"
            )

        return data

    def read_database(self, start=None, stop=None, database="interval", options=None):
        """
        The database is read from the top and down. So start date is the latest value
        and stop date is for the oldest values
        """
        msg = ReadDatabaseRequest(database=database, start=start, stop=stop).to_bytes()
        self.transport.send(msg)

        records = self._read_database()
        # TODO: add other parse configs

        parser = parse.CorusDataParser(
            parsing_config=parse.HOURLY_DATABASE_PARSE_CONFIG
        )
        data = [parser.parse(record) for record in records]

        return data

    def _read_database(self) -> List[bytes]:
        data = b""
        record_size: int = 0
        read_next = True
        is_first_frame = True
        retry_count = 0
        previous_frame_number: int = 0
        current_frame_number = -1

        while read_next:
            in_bytes = b""

            first_char = self.transport.recv(1)
            if not first_char == b"\x01":
                raise Exception("first char is not SOH")

            length = self.transport.recv(1)
            frame_data_length = int.from_bytes(bytes=length, byteorder="big")

            frame_data = self.transport.recv(frame_data_length)

            # Framenumber is little endian!
            frame_number_data = frame_data[:2]
            current_frame_number = (
                int.from_bytes(frame_number_data, "little") & 0b0111111111111111
            )

            end_char = self.transport.recv(1)
            if not end_char == b"\x03":
                raise Exception("end char not ETX")

            in_bytes += first_char + length + frame_data + end_char

            if is_first_frame:
                # record_size is only sent in first frame...
                record_size = int.from_bytes(frame_data[2:3], "big")
                data = data + frame_data[3:]

            else:
                data = data + frame_data[2:]
                if current_frame_number != (previous_frame_number + 1):
                    raise Exception("Data frames not received in order")

            crc = self.transport.recv(2)

            total_data = in_bytes + crc
            logger.debug(f"Total Data: {total_data!r}")

            if not utils.crc_valid(in_bytes, crc):
                # Send nack if crc is not valid
                logger.debug(
                    f"Message failed CRC validation. Message: {in_bytes!r}, "
                    f"received_crc: {crc!r}"
                )
                if retry_count >= 3:
                    raise Exception("Maximum amounts of retries done. Aborting.")
                self.transport.send(b"\x15")  # NACK
                retry_count += 1
                continue

            is_first_frame = False
            is_last_frame = bool(
                int.from_bytes(frame_number_data, "little") & 0b1000000000000000
            )

            if is_last_frame:
                read_next = False
            else:
                self.transport.send(b"\x06")  # ACK
                retry_count = 0  # Reset retry for a message part
                previous_frame_number = current_frame_number

        records = [data[i : i + record_size] for i in range(0, len(data), record_size)]
        return records
