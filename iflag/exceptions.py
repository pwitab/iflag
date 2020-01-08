class CorusClientError(Exception):
    """General error in CorusClient"""


class ProtocolError(CorusClientError):
    """Error in the data received from the device"""


class CommunicationError(CorusClientError):
    """Error in the communication with the device"""


class DataError(CorusClientError):
    """Problem with input data"""
