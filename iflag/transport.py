import time
import logging
import socket
from typing import Tuple, Optional

from iflag import utils, exceptions

logger = logging.getLogger(__name__)


class BaseTransport:
    TRANSPORT_REQUIRES_ADDRESS = True

    def __init__(self, timeout=30):
        self.timeout = timeout

    def connect(self):
        raise NotImplemented("Must be defined in subclass")

    def disconnect(self):
        raise NotImplemented("Must be defined in subclass")

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
                raise exceptions.CommunicationError(
                    f"Read in {self.__class__.__name__} timed out"
                )
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

        logger.debug(f"Received {in_data!r} over {self.__class__.__name__}")
        return in_data

    def send(self, data: bytes):
        """
        Will send data over the transport

        :param data:
        """
        self._send(data)
        logger.debug(f"Sent {data!r} over {self.__class__.__name__}")

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
        logger.info(f"Connecting to {self.address}")
        try:
            self.socket.connect(self.address)
        except (OSError, IOError, socket.timeout, socket.error) as e:
            raise exceptions.CommunicationError from e

    def disconnect(self):
        """
        Closes and removes the socket.
        """
        self.socket.close()
        self.socket = None
        logger.info(f"Closed connection to {self.address}")

    def _send(self, data: bytes):
        """
        Sends data over the socket.

        :param data:
        """
        try:
            self.socket.sendall(data)
        except (OSError, IOError, socket.timeout, socket.error) as e:
            raise exceptions.CommunicationError from e

    def _recv(self, chars=1):
        """
        Receives data from the socket.

        :param chars:
        """
        try:
            b = self.socket.recv(chars)
        except (OSError, IOError, socket.timeout, socket.error) as e:
            raise exceptions.CommunicationError from e
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
