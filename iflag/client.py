import logging
from datetime import datetime
from decimal import Decimal

from iflag.transport import TcpTransport, BaseTransport
from iflag.messages import ReadDatabaseRequest, ReadRequest, WriteData, WriteRequest
from iflag import parse, utils, exceptions
from iflag.data import IFlagParameter, DatabaseRecordParameter, CorusString, Float

from typing import Tuple, List, Any, Dict, Optional

logger = logging.getLogger(__name__)

DatabaseConfig = Dict[str, Dict[int, List[DatabaseRecordParameter]]]


class CorusClient:
    """
    Corus client class for interfacing with meters using the Corus protocol.
    """

    DATABASES = {"interval", "hourly", "daily", "monthly"}

    def __init__(
        self,
        transport: BaseTransport,
        database_layout: Optional[DatabaseConfig] = None,
        input_pulse_weight: Optional[Decimal] = None,
    ):
        """
        :param transport: Transport class to use for the Client.
        """
        self.database_layout = database_layout
        self.transport = transport
        self._input_pulse_weight: Optional[Decimal] = input_pulse_weight

    @classmethod
    def with_tcp_transport(
        cls,
        address: Tuple[str, int],
        database_layout: Optional[DatabaseConfig] = None,
        input_pulse_weight: Optional[Decimal] = None,
    ):
        """
        Creates a CorusClient with a TCP transport.

        :param input_pulse_weight: A decimal value that is used to extract correct value
                from some database record parameters.
        :param database_layout: Dict allowing to specify how the database records
               are constructed and how they are interpreted.
        :param address: TCP/IP address and port tuple
        """
        return cls(
            transport=TcpTransport(address),
            database_layout=database_layout,
            input_pulse_weight=input_pulse_weight,
        )

    def read_parameters(self, parameters: List[IFlagParameter]) -> dict:
        """
        Reads parameters from the device.
        :param parameters: List of parameters to read.
        :return: dict with all parameters that where requested.
        """

        parameter_ids = [parameter.id for parameter in parameters]

        logger.info(f"Reading parameters: {parameters}")
        try:
            in_data = self._read_parameters_by_id(parameter_ids)
        except (exceptions.ProtocolError, exceptions.CommunicationError) as e:
            raise exceptions.CorusClientError from e
        data = parse.parse_corus_response(in_data, parameters)
        logger.info(f"Received parameter data: {data}")
        return data

    def get_parameter_map_id(self) -> str:
        """
        All firmware versions have the parameter map id located at 0x5E. 
        It consists of FL_XXXXX where XXXX is the mapping id. In mapping files 
        the id can consists of both lower and upper case letters but to unify it this 
        function will only return lower case ids.
        """

        value: str = self.read_parameters(
            [IFlagParameter(id=0x5E, data_class=CorusString)]
        )[0x5E]
        map_id = value.split("_")[1]
        return map_id

    @property
    def input_pulse_weight(self):
        if self._input_pulse_weight is None:
            logger.info("Reading Impulse Weight from Meter")
            self._input_pulse_weight = self.read_parameters(
                [IFlagParameter(1, data_class=Float)]
            )[1]
            logger.info(f"Set input_pulse_weight={self._input_pulse_weight} on client")
        return self._input_pulse_weight

    def write_parameters(self, parameters: List[Tuple[IFlagParameter, Any]]) -> None:
        """
        Writes parameters to the device.
        :param parameters: List of tuples of the IFlagParameter and the values to write
        :return:
        """

        write_data = [
            WriteData(id=parameter.id, data=parameter.data_class(value).to_bytes())
            for parameter, value in parameters
        ]
        msg = WriteRequest(data=write_data)
        logger.info(f"Writing parameters: {parameters}")
        logger.info(f"Sending {msg}")
        try:
            self.transport.send(msg.to_bytes())
            ack = self.transport.recv(1)
        except (exceptions.ProtocolError, exceptions.CommunicationError) as e:
            raise exceptions.CorusClientError from e

        if ack != b"\x06":
            logger.info(f"Received non ACK on sending {msg}")
            raise exceptions.CommunicationError(f"Error in sending {msg}")

        logger.info(f"Parameters {parameters} sent and accepted")

    def read_database(
        self,
        database: str,
        start: Optional[datetime] = None,
        stop: Optional[datetime] = None,
        input_pulse_weight: Optional[Decimal] = None,
        database_layout: Optional[DatabaseConfig] = None,
    ) -> List[Dict[str, Any]]:
        """
        The database is read from the top and down. So start date is the latest value
        and stop date is for the oldest values.
        Available databases are: interval, hourly, daily and monthly.
        """

        if database not in self.DATABASES:
            raise exceptions.CorusClientError(
                f"Database {database!r} is not a valid database"
            )

        pulse_weight = input_pulse_weight or self.input_pulse_weight
        if pulse_weight is None:
            raise exceptions.CorusClientError(
                f"Trying to read database records without a predefined pulse weight. "
                f"Define it on client init or in the read_database call."
            )

        _database_layout = database_layout or self.database_layout
        if _database_layout is None:
            raise exceptions.CorusClientError(
                f"Trying to read database records without a predefined database layout."
                f"Define it on client init or in the read_database call."
            )

        msg = ReadDatabaseRequest(database=database, start=start, stop=stop)

        logger.info(f"Sending {msg!r}")
        try:
            self.transport.send(msg.to_bytes())
            records = self._read_database_data()
        except (exceptions.ProtocolError, exceptions.CommunicationError) as e:
            raise exceptions.CorusClientError from e

        if not records:
            return []

        record_length = len(records[0])
        try:
            record_parameters = _database_layout[database][record_length]
            return [
                parse.parse_corus_database_record(
                    record, record_parameters, pulse_weight
                )
                for record in records
            ]

        except KeyError:
            logger.error(
                f"No record definition in {database!r} database with length "
                f"of {record_length}"
            )
            raise exceptions.CorusClientError(
                "Unable to find parsing config for database that fit the record length"
            )

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

    def startup(self):
        """
        Similar sign on as IEC 62056-21. But no need to send a meter address. Device
        returns identification that has no special meaning. At least not over TCP.
        Then a standard Ack is sent.
        Then a "Password" exchange is done, but not really, just send the code PASS back
        and forth. So we just fast forward all of this to get to the correct state.
        """
        self.transport.connect()
        self._wakeup()
        logger.info(f"Initiating device communications")
        sign_on_message = b"/?!\r\n"
        self.transport.send(sign_on_message)
        ident = self.transport.simple_read(start_char=b"/", end_char=b"\x0a")
        ack_message = b"\x06\x30\x37\x36\x0d\x0a"
        self.transport.send(ack_message)
        pass_msg = self.transport.recv(6)
        # TODO: check the crc
        self.transport.send(pass_msg)
        ack = self.transport.recv(1)
        if ack != b"\x06":
            raise exceptions.ProtocolError("Ack not received after sign on")

    def shutdown(self):
        """
        Sends a BREAK message to the device to indicate end of communication.
        """
        logger.info(f"Sending break message")
        msg = b"\x01B0\x03!1"  # pre calculated CRC.
        self.transport.send(msg)
        self.transport.disconnect()

    def _read_parameters_by_id(self, parameters_ids: List[int]) -> bytes:
        """
        Parameters are read by their ID according to Corus documentation. Several
        parameters can be read one request and the response will order the data in the
        same order as the request sent the IDs.

        :param parameters_ids: List of ids to read.
        :return: bytes
        """
        msg = ReadRequest(parameters_ids)

        logger.info(f"Sending {msg!r}")
        self.transport.send(msg.to_bytes())
        read_data = self._read_response_data()
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
        _data = b""
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
                _data = _data + frame_data[3:]

            else:
                _data = _data + frame_data[2:]
                if current_frame_number != (previous_frame_number + 1):
                    raise exceptions.ProtocolError("Data frames not received in order")

            crc = self.transport.recv(2)

            total_data = in_bytes + crc

            logger.debug(f"Received data: {total_data.hex()!r}")

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

        records = [
            _data[i : i + record_size] for i in range(0, len(_data), record_size)
        ]
        return records

    def __repr__(self):
        return (
            f"{self.__class__.__name__}(transport={self.transport!r}, "
            f"database_layout={self.database_layout!r}, "
            f"input_pulse_weight={self._input_pulse_weight!r})"
        )
