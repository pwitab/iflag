import typing

from iflag import data
import attr

from iflag.data import CorusData


@attr.s(auto_attribs=True)
class ParseConfigItem:
    name: str
    data_class: typing.Type[CorusData]


INTERVAL_DATABASE_PARSE_CONFIG: typing.List[ParseConfigItem] = [
    ParseConfigItem(name="record_duration", data_class=data.Byte),
    ParseConfigItem(name="status", data_class=data.Byte),
    ParseConfigItem(name="end_date", data_class=data.Date),
    ParseConfigItem(name="consumption_unconverted", data_class=data.Word),
    ParseConfigItem(name="consumption_converted", data_class=data.ULong),
    ParseConfigItem(name="counter_unconverted", data_class=data.Word),
    ParseConfigItem(name="counter_converted", data_class=data.ULong),
    ParseConfigItem(name="temperature_minimum", data_class=data.Float1),
    ParseConfigItem(name="temperature_maximum", data_class=data.Float1),
    ParseConfigItem(name="temperature_average", data_class=data.Float1),
    ParseConfigItem(name="pressure_minimum", data_class=data.Float2),
    ParseConfigItem(name="pressure_maximum", data_class=data.Float2),
    ParseConfigItem(name="pressure_average", data_class=data.Float2),
    ParseConfigItem(name="flowrate_unconverted_minimum", data_class=data.Float3),
    ParseConfigItem(name="flowrate_unconverted_maximum", data_class=data.Float3),
    ParseConfigItem(name="flowrate_converted_minimum", data_class=data.Float3),
    ParseConfigItem(name="flowrate_converted_maximum", data_class=data.Float3),
    ParseConfigItem(name="none_data_1", data_class=data.Null4),
    ParseConfigItem(name="flowrate_unconverted_average", data_class=data.Float3),
    ParseConfigItem(name="flowrate_converted_average", data_class=data.Float3),
    ParseConfigItem(name="start_date", data_class=data.Date),
    ParseConfigItem(name="none_data_2", data_class=data.Null2),
]

# interval log and hourly log has the same structure
HOURLY_DATABASE_PARSE_CONFIG: typing.List[
    ParseConfigItem
] = INTERVAL_DATABASE_PARSE_CONFIG

DAILY_DATABASE_PARSE_CONFIG: typing.List[ParseConfigItem] = [
    ParseConfigItem(name="record_duration", data_class=data.Word),
    ParseConfigItem(name="status", data_class=data.Byte),
    ParseConfigItem(name="end_date", data_class=data.Date),
    ParseConfigItem(name="consumption_unconverted", data_class=data.EWord),
    ParseConfigItem(name="consumption_converted", data_class=data.EULong),
    ParseConfigItem(name="counter_unconverted", data_class=data.EWord),
    ParseConfigItem(name="counter_converted", data_class=data.EULong),
    ParseConfigItem(name="temperature_minimum", data_class=data.Float1),
    ParseConfigItem(name="temperature_maximum", data_class=data.Float1),
    ParseConfigItem(name="temperature_average", data_class=data.Float1),
    ParseConfigItem(name="pressure_minimum", data_class=data.Float2),
    ParseConfigItem(name="pressure_maximum", data_class=data.Float2),
    ParseConfigItem(name="pressure_average", data_class=data.Float2),
    ParseConfigItem(name="flowrate_unconverted_minimum", data_class=data.Float3),
    ParseConfigItem(name="flowrate_unconverted_maximum", data_class=data.Float3),
    ParseConfigItem(name="flowrate_converted_minimum", data_class=data.Float3),
    ParseConfigItem(name="flowrate_converted_maximum", data_class=data.Float3),
    ParseConfigItem(name="none_data_1", data_class=data.Null4),
    ParseConfigItem(name="flowrate_unconverted_average", data_class=data.Float3),
    ParseConfigItem(name="flowrate_converted_average", data_class=data.Float3),
    ParseConfigItem(name="start_date", data_class=data.Date),
    ParseConfigItem(name="none_data_2", data_class=data.Null2),
]

MONTHLY_DATABASE_PARSE_CONFIG: typing.List[ParseConfigItem] = [
    ParseConfigItem(name="record_duration", data_class=data.Word),
    ParseConfigItem(name="status", data_class=data.Byte),
    ParseConfigItem(name="end_date", data_class=data.Date),
    ParseConfigItem(name="consumption_unconverted", data_class=data.EWord),
    ParseConfigItem(name="consumption_converted", data_class=data.EULong),
    ParseConfigItem(name="counter_unconverted", data_class=data.EWord),
    ParseConfigItem(name="counter_converted", data_class=data.EULong),
    ParseConfigItem(name="temperature_minimum", data_class=data.Float1),
    ParseConfigItem(name="temperature_maximum", data_class=data.Float1),
    ParseConfigItem(name="temperature_average", data_class=data.Float1),
    ParseConfigItem(name="pressure_minimum", data_class=data.Float2),
    ParseConfigItem(name="pressure_maximum", data_class=data.Float2),
    ParseConfigItem(name="pressure_average", data_class=data.Float2),
    ParseConfigItem(name="flowrate_unconverted_minimum", data_class=data.Float3),
    ParseConfigItem(name="flowrate_unconverted_maximum", data_class=data.Float3),
    ParseConfigItem(name="flowrate_converted_minimum", data_class=data.Float3),
    ParseConfigItem(name="flowrate_converted_maximum", data_class=data.Float3),
    ParseConfigItem(name="none_data_1", data_class=data.Null4),
    ParseConfigItem(name="index_unconverted", data_class=data.Index),
    ParseConfigItem(name="index_converted", data_class=data.Index),
    ParseConfigItem(name="counter_unconverted", data_class=data.Index),
    ParseConfigItem(name="counter_converted", data_class=data.Index),
    ParseConfigItem(
        name="consumption_unconverted_interval_maximum", data_class=data.Word
    ),
    ParseConfigItem(
        name="consumption_unconverted_interval_maximum_date", data_class=data.Date
    ),
    ParseConfigItem(
        name="consumption_converted_interval_maximum", data_class=data.ULong
    ),
    ParseConfigItem(
        name="consumption_converted_interval_maximum_date", data_class=data.Date
    ),
    ParseConfigItem(name="flowrate_unconverted_average", data_class=data.Float3),
    ParseConfigItem(name="flowrate_converted_average", data_class=data.Float3),
    ParseConfigItem(name="start_date", data_class=data.Date),
    ParseConfigItem(name="none_data_2", data_class=data.Null2),
]


class CorusDataParser:
    """
    Parser class to handle Corus data conversion.

    """
    def __init__(self, parsing_config: typing.Sequence[ParseConfigItem]):
        self.parsing_config = parsing_config

    @property
    def parse_length(self) -> int:
        """
        Calculates how long the data should be
        :return: data length
        """
        return sum([config.data_class.length for config in self.parsing_config])

    def parse(self, in_data: bytes) -> dict:
        """
        Converts corus data to a result dict by using the parsing config.
        :param in_data: in_data
        :return:
        """
        if len(in_data) != self.parse_length:
            raise ValueError(
                f"In data is not of correct length. Should be {self.parse_length} "
                f"but is {len(in_data)}"
            )
        out_data = {}
        index = 0
        for item in self.parsing_config:
            end_index = index + item.data_class.length
            data = in_data[index:end_index]
            index = end_index
            data_instance = item.data_class.from_bytes(data)
            out_data[item.name] = data_instance.value

        return out_data
