from typing import Sequence, Dict, Any
from decimal import Decimal

from iflag.data import IFlagParameter, DatabaseRecordParameter


def parse_corus_response(
    response_data: bytes, parameters: Sequence[IFlagParameter]
) -> Dict[int, Any]:
    """
    Converts corus response bytes data to a result dict by using the parameter id as
    key.

    :param parameters: Sequence of IFlagParameters. The position of the elements
        corresponds to the position of the data in response_data.
    :param response_data: bytes of corus data
    :return: dict
    """
    correct_length = sum([parameter.data_class.LENGTH for parameter in parameters])
    if len(response_data) != correct_length:
        raise ValueError(
            f"In data is not of correct length. Should be {correct_length} "
            f"but is {len(response_data)}"
        )
    out_data = {}
    index = 0
    for parameter in parameters:
        end_index = index + parameter.data_class.LENGTH
        _data = response_data[index:end_index]
        index = end_index
        data_instance = parameter.data_class.from_bytes(_data)
        value = data_instance.value
        if value is None:
            continue
        out_data[parameter.id] = value

    return out_data


def parse_corus_database_record(
    record: bytes,
    parameters: Sequence[DatabaseRecordParameter],
    input_pulse_weight: Decimal,
) -> Dict[str, Any]:
    """
    Converts a corus database record to a result dict with the name of the
    DatabaseRecordParameter as key.
    :param input_pulse_weight: The impulse weight of the meter to scale the result if
        needed
    :param parameters: Sequence of DatabaseRecordParameters. The positions in the list reflects the data position in the record data.
    :param record: The record data in bytes.
    :return:
    """
    correct_length = sum([parameter.data_class.LENGTH for parameter in parameters])
    if len(record) != correct_length:
        raise ValueError(
            f"In data is not of correct length. Should be {correct_length} "
            f"but is {len(record)}"
        )
    out_data = {}
    index = 0
    for parameter in parameters:
        end_index = index + parameter.data_class.LENGTH
        data = record[index:end_index]
        index = end_index
        data_instance = parameter.data_class.from_bytes(data)
        value = data_instance.value
        if value is None:
            continue
        if parameter.affected_by_pulse_input:
            value = value * input_pulse_weight

        if parameter.multiplied:
            value = value / parameter.multiplied

        out_data[parameter.name] = value

    return out_data
