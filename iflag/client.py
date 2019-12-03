import logging
from iflag.transport import TcpTransport, BaseTransport
from typing import Tuple

logger = logging.getLogger(__name__)

class CorusClient:

    def __init__(self, transport: BaseTransport, password: str = '00000000'):
        self.transport = transport
        self.password = password

    @classmethod
    def with_tcp_transport(cls, address: Tuple[str, int], password: str = '00000000'):
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
        if response != b'\x00\x00\x00':
            raise Exception('Received non null wakeup response')

    def sign_on(self):
        """
        Similar sign on as IEC 62056-21. But no need to send a meter address. Device
        returns identification that has no special meaning. At least not over TCP.
        Then a standard Ack is sent.
        Then a "Password" exchange is done, but not really, just send the code PASS back
        and forth. So we just fast forward all of this to get to the correct state.
        """

        sign_on_message = b'/?!\r\n'
        self.transport.send(sign_on_message)
        ident = self.transport.simple_read(start_char="/", end_char="\x0a")
        ack_message = b'\x06\x30\x37\x30\x0d\x0a'
        self.transport.send(ack_message)
        pass_msg = self.transport.recv(6)
        # TODO: check the crc
        self.transport.send(pass_msg)
        ack = self.transport.recv(1)
        if ack != b'\x06':
            raise Exception('Ack not refeived after signon')

    def read_database(self, start=None, stop=None, database=None, options=None):
        request_msg = bytes.fromhex('01be0d00f9ff0f38000000000000000003fa0e')
        self.transport.send(request_msg)


        self.transport.corus_read()
