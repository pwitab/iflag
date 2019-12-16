import socket

HOST = '10.70.138.159'
PORT = 8000

METER_ADDRESS = b''
#METER_ADDRESS = b''

METER_PASSWORD = b'00000000'


def make_init_message(address):  # NOTE: according to standard, the address can be up to 32*something long
    """Returns initiation message for given address.

    If the address is less than 8 chars extra '0' are added to the address.
    If the address is more than 8 chars, an Exception is raised.
    """

    if len(address) is 0:  # If the address is ''. Works when computer is only wired to one device
        message = b'\x2f\x3f' + address + b'\x21\x0d\x0a'
        return message
    #if len(address) > 8:
    #    raise Exception()
    if 0 < len(
            address) < 8:  # Adding 'leading zeros' if the address is not 8 chars long
        n = 8 - len(address)
        address = '{}'.format(n * '0') + address
    message = b'\x2f\x3f' + address + b'\x21\x0d\x0a'
    return message


def remove_parity(input):
    """Function that converts 8bit byte string into 7bit byte string by removing the parity bit"""
    data_list = []
    for byte in input:
        temp = byte & 0x7f
        temp = chr(temp).encode('latin-1')
        data_list.append(temp)
    return b''.join(data_list)


def add_parity(input_string):
    """Function to add (even) parity to a string of hex byte representations.

    For example '2f 3f 37 30' -> 'af 3f b7 30'.
    """
    output = []  # Create empty list for output
    for x in input_string:  # Loop through all bytes in input_string
        nonzero_bit_count = bin(x).count(
            '1')  # Count non-zero bits (i.e. 1s)
        if nonzero_bit_count % 2 is 1:  # If uneven amount of bits, parity is needed
            temp = x | 0x80  # Add parity using bitwise OR with 0x80 (1000 000)
            output.append(chr(temp))
        else:  # Parity bit not needed
            output.append(chr(x))  # Byte is added unchanged
    output_string = ''.join(output)  # Converts list to string
    return output_string.encode('latin-1')


if __name__ == '__main__':

    while True:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(30)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)  # Keep the socket alive
        print('Connecting to socket:', HOST, ':', str(PORT))

        sock.connect((HOST, PORT))
        print('Connected!')

        initiate_message = bytes(200)
        #initiate_message = make_init_message(METER_ADDRESS)  # Get message from protoco
        #initiate_message = initiate_message.encode('latin-1')
        #initiate_message = add_parity(initiate_message)  # Converts to eight bit
        print(type(initiate_message))
        print(initiate_message)

        sock.sendall(initiate_message)

        response = sock.recv(3)
        print(response)

        #sock.sendall(initiate_message)
        print(initiate_message)

        sock.sendall(make_init_message(b''))
        print(make_init_message(b''))

        response = sock.recv(17)
        print(response)

        sock.sendall(b'\x06\x30\x37\x30\x0d\x0a')
        print(b'\x06\x30\x37\x30\x0d\x0a')

        result = sock.recv(10)
        print(result)

        sock.sendall(b'PASS\xe0\xae')
        print(b'PASS\xe0\xae')

        response = sock.recv(10)
        print(response)

        # read out alarms
        # to_send = ''01be0d047a000000000000000000000003'c1e3'
        # sock.sendall(bytes.fromhex(to_send))
        #
        # response = sock.recv(300)
        #
        # sock.sendall(b'\x06')
        # response += sock.recv(300)
        #
        # sock.sendall(b'\x06')
        # response += sock.recv(300)
        #
        # sock.sendall(b'\x06')
        # response += sock.recv(300)
        #
        # sock.sendall(b'\x06')
        # response += sock.recv(300)
        #
        # sock.sendall(b'\x06')
        # response += sock.recv(300)
        #
        # print(response.split(b'\xff\xff\xff\xff'))

        # read out interval
        to_send = '01be0d00f9ff0f38000000000000000003fa0e'
        sock.sendall(bytes.fromhex(to_send))
        while True:
            response = sock.recv(600)
            sock.sendall(b'\x06')
            print(response)

        sock.close()










