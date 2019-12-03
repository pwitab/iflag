import time
import logging

import socket
from typing import Tuple, Optional

from iflag import constants, utils

logger = logging.getLogger(__name__)


class BaseTransport:
    TRANSPORT_REQUIRES_ADDRESS = True

    def __init__(self, timeout=30):
        self.timeout = timeout

    def connect(self):
        raise NotImplemented("Must be defined in subclass")

    def disconnect(self):
        raise NotImplemented("Must be defined in subclass")

    def corus_read(self):

        data = b""
        record_size: Optional[int] = None
        read_next = True
        is_first_frame = True
        retry_count = 0
        previous_frame_number: Optional[int] = None
        current_frame_number = 0

        while read_next:
            in_bytes = b""

            first_char = self.recv(1)
            if not first_char == b"\x01":
                raise Exception("first char is not SOH")

            lenght = self.recv(1)
            frame_data_lenght = int.from_bytes(bytes=lenght, byteorder="big")

            frame_data = self.recv(frame_data_lenght)

            # Framenumber is little endian!
            frame_number_data = frame_data[:2]
            current_frame_number = (
                int.from_bytes(frame_number_data, "little") & 0b0111111111111111
            )

            end_char = self.recv(1)
            if not end_char == b"\x03":
                raise Exception("end char not ETX")

            in_bytes += first_char + lenght + frame_data + end_char

            if is_first_frame:
                # record_size is only sent in first frame...
                record_size = int.from_bytes(frame_data[2:3], "big")
                data = data + frame_data[3:]

            else:
                data = data + frame_data[2:]
                if current_frame_number != (previous_frame_number + 1):
                    raise Exception("Data frames not received in order")

            crc = self.recv(2)

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
                self.send(b"\x15")
                retry_count += 1
                continue

            is_first_frame = False
            is_last_frame = bool(
                int.from_bytes(frame_number_data, "little") & 0b1000000000000000
            )

            if is_last_frame:
                read_next = False
            else:
                self.send(b"\x06")
                retry_count = 0  # Reset retry for a message part
                previous_frame_number = current_frame_number


        # TODO: split records and give them timestamps.


        return data

    def read(self, timeout=None):
        """
        Will read a normal readout. Supports both full and partial block readout.
        When using partial blocks it will recreate the messages as it was not sent with
        partial blocks

        :param timeout:
        :return:
        """
        start_chars = [b"\x01", b"\x02"]
        end_chars = [b"\x03", b"\x04"]
        total_data = b""
        packets = 0
        start_char_received = False
        start_char = None
        end_char = None
        timeout = timeout or self.timeout

        while True:

            in_data = b""
            duration = 0
            start_time = time.time()
            while True:
                b = self.recv(1)
                duration = time.time() - start_time
                if duration > self.timeout:
                    raise TimeoutError(f"Read in {self.__class__.__name__} timed out")
                if not start_char_received:
                    # is start char?
                    if b in start_chars:
                        in_data += b
                        start_char_received = True
                        start_char = b
                        continue
                    else:
                        continue
                else:
                    # is end char?
                    if b in end_chars:
                        in_data += b
                        end_char = b
                        break
                    else:
                        in_data += b
                        continue

            packets += 1

            bcc = self.recv(1)
            in_data += bcc
            logger.debug(
                f"Received {in_data!r} over transport: {self.__class__.__name__}"
            )

            if start_char == b"\x01":
                # This is a command message, probably Password challange.
                total_data += in_data
                break

            if end_char == b"\x04":  # EOT (partial read)
                # we received a partial block
                if not utils.bcc_valid(in_data):
                    # Nack and read again
                    self.send(constants.NACK.encode(constants.ENCODING))
                    continue
                else:
                    # ack and read next
                    self.send(constants.ACK.encode(constants.ENCODING))
                    # remove bcc and eot and add line end.
                    in_data = in_data[:-2] + constants.LINE_END.encode(
                        constants.ENCODING
                    )
                    if packets > 1:
                        # remove the leading STX
                        in_data = in_data[1:]

                    total_data += in_data
                    continue

            if end_char == b"\x03":
                # Either it was the only message or we got the last message.
                if not utils.bcc_valid(in_data):
                    # Nack and read again
                    self.send(constants.NACK.encode(constants.ENCODING))
                    continue
                else:
                    if packets > 1:
                        in_data = in_data[1:]  # removing the leading STX
                    total_data += in_data
                    if packets > 1:
                        # The last bcc is not correct compared to the whole
                        # message. But we have verified all the bccs along the way so
                        # we just compute it so the message is usable.
                        total_data = utils.add_bcc(total_data[:-1])

                    break

        return total_data

    def simple_read(self, start_char, end_char, timeout=None):
        """
        A more flexible read for use with some messages.
        """
        _start_char = utils.ensure_bytes(start_char)
        _end_char = utils.ensure_bytes(end_char)

        in_data = b""
        start_char_received = False
        timeout = timeout or self.timeout
        duration = 0
        start_time = time.time()
        while True:
            b = self.recv(1)
            duration = time.time() - start_time
            if duration > self.timeout:
                raise TimeoutError(f"Read in {self.__class__.__name__} timed out")
            if not start_char_received:
                # is start char?
                if b == _start_char:
                    in_data += b
                    start_char_received = True
                    continue
                else:
                    continue
            else:
                # is end char?
                if b == _end_char:
                    in_data += b
                    break
                else:
                    in_data += b
                    continue

        logger.debug(f"Received {in_data!r} over transport: {self.__class__.__name__}")
        return in_data

    def send(self, data: bytes):
        """
        Will send data over the transport

        :param data:
        """
        self._send(data)
        logger.debug(f"Sent {data!r} over transport: {self.__class__.__name__}")

    def _send(self, data: bytes):
        """
        Transport dependant sending functionality.

        :param data:
        """
        raise NotImplemented("Must be defined in subclass")

    def recv(self, chars):
        """
        Will receive data over the transport.

        :param chars:
        """
        return self._recv(chars)

    def _recv(self, chars):
        """
        Transport dependant sending functionality.

        :param chars:
        """
        raise NotImplemented("Must be defined in subclass")

    def switch_baudrate(self, baud):
        """
        The protocol defines a baudrate switchover process. Though it might not be used
        in all available transports.

        :param baud:
        """
        raise NotImplemented("Must be defined in subclass")


class TcpTransport(BaseTransport):
    """
        Transport class for TCP/IP communication.
        """

    def __init__(self, address: Tuple[str, int], timeout=30):

        super().__init__(timeout=timeout)
        self.address = address
        self.socket = self._get_socket()

    def connect(self):
        """
        Connects the socket to the device network interface.
        """

        if not self.socket:
            self.socket = self._get_socket()
        logger.debug(f"Connecting to {self.address}")
        self.socket.connect(self.address)

    def disconnect(self):
        """
        Closes and removes the socket.
        """
        self.socket.close()
        self.socket = None

    def _send(self, data: bytes):
        """
        Sends data over the socket.

        :param data:
        """
        self.socket.sendall(data)

    def _recv(self, chars=1):
        """
        Receives data from the socket.

        :param chars:
        """
        try:
            b = self.socket.recv(chars)
        except (OSError, IOError, socket.timeout, socket.error) as e:
            raise TransportError from e
        return b

    def switch_baudrate(self, baud):
        """
        Baudrate has not meaning in TCP/IP so we just dont do anything.

        :param baud:
        """
        pass

    def _get_socket(self):
        """
        Create a correct socket.
        """
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(self.timeout)
        return s

    def __repr__(self):
        return (
            f"{self.__class__.__name__}("
            f"address={self.address!r}, "
            f"timeout={self.timeout!r}"
        )
