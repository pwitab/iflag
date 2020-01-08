import logging
from contextlib import contextmanager

from iflag.transport import TcpTransport, BaseTransport
from iflag.messages import ReadDatabaseRequest, ReadRequest, WriteData, WriteRequest
from iflag import parse, utils, exceptions
from iflag.data import PARAMETERS_BY_NAME

from typing import Tuple, List


logger = logging.getLogger(__name__)


class CorusClient:
    """
    Corus client class for interfacing with meters using the Corus protocol.
    """

    def __init__(self, transport: BaseTransport):
        """
        :param transport: Transport class to use for the Client.
        """
        self.transport = transport

    def __repr__(self):
        return f"{self.__class__.__name__}(transport={self.transport!r})"

    @classmethod
    def with_tcp_transport(cls, address: Tuple[str, int]):
        """
        Creates a CorusClient with a TCP transport.

        :param address: TCP/IP address and port tuple
        :return:
        """
        return cls(transport=TcpTransport(address))

    def read_parameters(self, parameters: List[str]) -> dict:
        """
        Reads parameters from the device.
        :param parameters: List of parameters to read.
        :return: dict with all parameters that where requested.
        """
        # verify valid parameters:
        if not all(
            [(parameter in PARAMETERS_BY_NAME.keys()) for parameter in parameters]
        ):
            raise exceptions.CorusClientError(
                f"parameter_names contains unknown parameters, check documentation "
                f"for proper parameter names."
            )

        parameter_ids = [PARAMETERS_BY_NAME[parameter].id for parameter in parameters]
        parse_config = [
            parse.ParseConfigItem(
                name=PARAMETERS_BY_NAME[parameter].name,
                data_class=PARAMETERS_BY_NAME[parameter].data_class,
            )
            for parameter in parameters
        ]
        parser = parse.CorusDataParser(parsing_config=parse_config)

        logger.info(f"Reading parameters: {parameters}")
        try:
            in_data = self._read_parameters_by_id(parameter_ids)
        except (exceptions.ProtocolError, exceptions.CommunicationError) as e:
            raise exceptions.CorusClientError from e

        data = parser.parse(in_data)
        return data

    def write_parameters(self, parameters: dict) -> None:
        """
        Writes parameters to the device.
        :param parameters: Dict with parameters names as keys and parameter value as
            value
        :return:
        """
        if not all(
            [
                (parameter in PARAMETERS_BY_NAME.keys())
                for parameter in parameters.keys()
            ]
        ):
            raise exceptions.CorusClientError(
                f"parameter_names contains unknown parameters, check documentation "
                f"for proper parameter names."
            )

        # Check if writeable
        for parameter in parameters:
            if not PARAMETERS_BY_NAME[parameter].write:
                raise exceptions.DataError(f"Parameter {parameter} is not writable")

        write_data = [
            WriteData(
                id=PARAMETERS_BY_NAME[parameter].id,
                data=PARAMETERS_BY_NAME[parameter]
                .data_class(parameters[parameter])
                .to_bytes(),
            )
            for parameter in parameters.keys()
        ]

        msg = WriteRequest(data=write_data)
        logger.info(f"Writing parameters: {parameters}")
        with self._session() as session:
            logger.info(f"Sending {msg}")
            try:
                session.transport.send(msg.to_bytes())
                ack = session.transport.recv(1)
            except (exceptions.ProtocolError, exceptions.CommunicationError) as e:
                raise exceptions.CorusClientError from e

        if ack != b"\x06":
            logger.info(f"Received non ACK on sending {msg}")
            raise exceptions.CommunicationError(f"Error in sending {msg}")

        logger.info(f"Parameters {parameters} received and accepted")

    def read_database(self, start=None, stop=None, database="interval") -> List[dict]:
        """
        The database is read from the top and down. So start date is the latest value
        and stop date is for the oldest values.
        Available databases are: interval, hourly, daily and monthly.
        """
        database_parse_config_map = {
            "interval": parse.INTERVAL_DATABASE_PARSE_CONFIG,
            "hourly": parse.HOURLY_DATABASE_PARSE_CONFIG,
            "daily": parse.DAILY_DATABASE_PARSE_CONFIG,
            "monthly": parse.MONTHLY_DATABASE_PARSE_CONFIG,
        }
        if database not in database_parse_config_map.keys():
            raise exceptions.CorusClientError(
                f"Database {database} is not a valid database"
            )
        parser = parse.CorusDataParser(
            parsing_config=database_parse_config_map[database]
        )
        msg = ReadDatabaseRequest(database=database, start=start, stop=stop)

        with self._session() as session:
            logger.info(f"Sending {msg!r}")
            try:
                session.transport.send(msg.to_bytes())
                records = session._read_database_data()
            except (exceptions.ProtocolError, exceptions.CommunicationError) as e:
                raise exceptions.CorusClientError from e

        data = [parser.parse(record) for record in records]
        return data

    @contextmanager
    def _session(self):
        """
        Simple internal session handling to make sure we connect properly and disconnect
        properly at each interaction.
        :return:
        """
        logger.info(f"Starting session to {self}")
        self.transport.connect()
        self._wakeup()
        self._startup()
        yield self
        self._break()
        self.transport.disconnect()
        logger.info(f"Ended session to {self}")

    def _wakeup(self):
        """
        Similar to IEC62056-21 it is needed to send a sequence of null bytes to the
        device for it to wake up the interface. Protocol docs says at least 12 bytes but
        other software uses 200 bytes. We will stick to 200 bytes to not get any issues.
        The device should return 3 null bytes when it is ready.
        """
        wakeup_data = bytes(200)
        logger.info(f"Sending wakeup sequence")
        self.transport.send(wakeup_data)
        response = self.transport.recv(3)
        if response != b"\x00\x00\x00":
            raise exceptions.ProtocolError(
                f"Received non null wakeup response: {response!r}"
            )
        logger.info(f"Received proper wakeup response")

    def _startup(self):
        """
        Similar sign on as IEC 62056-21. But no need to send a meter address. Device
        returns identification that has no special meaning. At least not over TCP.
        Then a standard Ack is sent.
        Then a "Password" exchange is done, but not really, just send the code PASS back
        and forth. So we just fast forward all of this to get to the correct state.
        """
        logger.info(f"Initiating device communications")
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
            raise exceptions.ProtocolError("Ack not received after sign on")

    def _break(self):
        """
        Sends a BREAK message to the device to indicate end of communication.
        """
        logger.info(f"Sending break message")
        msg = b"\x01B0\x03!1"  # pre calculated CRC.
        self.transport.send(msg)

    def _read_parameters_by_id(self, parameters_ids: List[int]) -> bytes:
        """
        Parameters are read by their ID according to Corus documentation. Several
        parameters can be read one request and the response will order the data in the
        same order as the request sent the IDs.

        :param parameters_ids: List of ids to read.
        :return: bytes
        """
        msg = ReadRequest(parameters_ids)
        with self._session() as session:
            logger.info(f"Sending {msg!r}")
            session.transport.send(msg.to_bytes())
            read_data = session._read_response_data()
        return read_data

    def _read_response_data(self) -> bytes:
        """
        Reads the response data for a read request.
        :return: Response data
        """
        in_bytes = b""

        first_char = self.transport.recv(1)
        if not first_char == b"\x01":
            raise exceptions.ProtocolError("first char is not SOH")

        length_byte = self.transport.recv(1)
        data_length = int.from_bytes(bytes=length_byte, byteorder="big")

        data = self.transport.recv(data_length)

        end_char = self.transport.recv(1)
        if not end_char == b"\x03":
            raise exceptions.ProtocolError("end char not ETX")

        in_bytes += first_char + length_byte + data + end_char

        crc = self.transport.recv(2)

        total_data = in_bytes + crc
        logger.debug(f"Received {total_data!r}")

        if not utils.crc_valid(in_bytes, crc):
            # Send nack if crc is not valid
            logger.debug(
                f"Message failed CRC validation. Message: {in_bytes!r}, "
                f"received_crc: {crc!r}"
            )
            raise exceptions.ProtocolError("Failed CRC check")

        return data

    def _read_database_data(self) -> List[bytes]:
        """
        Reads the response data for a database read request. The rules for receiving are
        a but tricky, mainly because first frame have extra data. It is described in
        more detail in the protocol documentation.
        :return: Response data
        """
        data = b""
        record_size: int = 0
        read_next = True
        is_first_frame = True
        retry_count = 0
        previous_frame_number: int = 0
        current_frame_number = -1

        logger.debug("Initiating database read")

        while read_next:
            in_bytes = b""

            first_char = self.transport.recv(1)
            if not first_char == b"\x01":
                raise exceptions.ProtocolError("first char is not SOH")

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
                raise exceptions.ProtocolError("end char not ETX")

            in_bytes += first_char + length + frame_data + end_char

            if is_first_frame:
                # record_size is only sent in first frame...
                record_size = int.from_bytes(frame_data[2:3], "big")
                if record_size == 0:
                    # en empty response is indicated by the first frame alos being
                    # the last frame and record size is 0.
                    raise exceptions.ProtocolError(
                        "Empty response"
                    )  # TODO: better handling
                data = data + frame_data[3:]

            else:
                data = data + frame_data[2:]
                if current_frame_number != (previous_frame_number + 1):
                    raise exceptions.ProtocolError("Data frames not received in order")

            crc = self.transport.recv(2)

            total_data = in_bytes + crc

            logger.debug(f"Received data: {total_data!r}")

            if not utils.crc_valid(in_bytes, crc):
                # Send nack if crc is not valid
                logger.debug(
                    f"Message failed CRC validation. Message: {in_bytes!r}, "
                    f"received_crc: {crc!r}"
                )
                if retry_count >= 3:
                    raise exceptions.CommunicationError(
                        "Maximum amounts of retries done. Aborting."
                    )
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
