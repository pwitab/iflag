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

    def read_database(self):

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

        records = [data[i:i+record_size] for i in range(0, len(data), record_size)]
        return records


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

class TransportError(Exception):
    pass


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
