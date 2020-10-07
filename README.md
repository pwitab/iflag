# iflag

A Python library for the Itron / Actaris IFLAG and Corus protocol

## Installing

Install via pip, python 3.6+ only

```pip install iflag```

## About

iflag is a library focused on reading and writing data to devices using the IFLAG or 
Corus protocol. Mainly Itron / Actaris gas volume converters. Communication is done over 
TCP/IP

## Features

The library is now only focused on using Single Address Mode (SAM) of the Corus protocol
to access data. SEVC-D parameters of I-FLAG is not supported.

* Read parameters
* Write parameters
* Read databases (logs), event log not yet implemented

## Usage

- Different firmware versions have different ID for each parameter. But the 
  parameter_id_map is always on id `0x5e`. 
  So the mapping should be known beforehand or it should be read from the device before 
  reading more values.
  
- Different firmware versions also have different database record layout. You will need 
  to supply a mapping of how the databases looks like for the meters you want to read.
  A default mapping is not supplied since it would infer opinionated interpretation of 
  some values.
  
  You should create a mapping like: `Dict[str, Dict[int, List[DatabaseRecordParameter]]]`
  `interval` is the database and `52` is the length of the database record. A list of
   `DatabaseRecordParameter` in the order they are appearing in the data base record 
   will make it possible to convert the bytes into python values.
  
  Ex:
```python
  {
    "interval": {
        52: [
            DatabaseRecordParameter(name="record_duration", data_class=data.Byte),
            DatabaseRecordParameter(name="status", data_class=data.Byte),
            DatabaseRecordParameter(name="end_date", data_class=data.Date),
            DatabaseRecordParameter(
                name="consumption_interval_unconverted",
                data_class=data.Word,
                affected_by_pulse_input=True,
            ),
            DatabaseRecordParameter(
                name="consumption_interval_converted",
                data_class=data.ULong,
                affected_by_pulse_input=True,
            ),
            DatabaseRecordParameter(
                name="counter_interval_unconverted",
                data_class=data.Word,
                affected_by_pulse_input=True,
            ),
            DatabaseRecordParameter(
                name="counter_interval_converted",
                data_class=data.ULong,
                affected_by_pulse_input=True,
            ),
            DatabaseRecordParameter(
                name="temperature_interval_minimum", data_class=data.Float1
            ),
            DatabaseRecordParameter(
                name="temperature_interval_maximum", data_class=data.Float1
            ),
            DatabaseRecordParameter(
                name="temperature_interval_average", data_class=data.Float1
            ),
            DatabaseRecordParameter(
                name="pressure_interval_minimum", data_class=data.Float2
            ),
            DatabaseRecordParameter(
                name="pressure_interval_maximum", data_class=data.Float2
            ),
            DatabaseRecordParameter(
                name="pressure_interval_average", data_class=data.Float2
            ),
            DatabaseRecordParameter(
                name="flowrate_unconverted_interval_minimum",
                data_class=data.Float3,
                affected_by_pulse_input=True,
            ),
            DatabaseRecordParameter(
                name="flowrate_unconverted_interval_maximum",
                data_class=data.Float3,
                affected_by_pulse_input=True,
            ),
            DatabaseRecordParameter(
                name="flowrate_converted_interval_minimum",
                data_class=data.Float3,
                affected_by_pulse_input=True,
            ),
            DatabaseRecordParameter(
                name="flowrate_converted_interval_maximum",
                data_class=data.Float3,
                affected_by_pulse_input=True,
            ),
            DatabaseRecordParameter(name="none_data_1", data_class=data.Null4),
            DatabaseRecordParameter(
                name="flowrate_unconverted_interval_average",
                data_class=data.Float3,
                affected_by_pulse_input=True,
            ),
            DatabaseRecordParameter(
                name="flowrate_converted_interval_average",
                data_class=data.Float3,
                affected_by_pulse_input=True,
            ),
            DatabaseRecordParameter(name="start_date", data_class=data.Date),
            DatabaseRecordParameter(name="none_data_2", data_class=data.Null2),
        ]
    }
} 
```

- Good to know: There are several different float formats due to memory constraints in
    the protocol and device. All floats are handled as `decimal.Decimal` in Python to 
    not have float rounding errors.

### Read parameters:

``python

from iflag import CorusClient
from iflag.data import CorusString, Index
from iflag.parse import IFlagParameter
from decimal import Decimal

client = CorusClient.with_tcp_transport(address=("localhost", 4000))
# Read single value
client.read_parameters([IFlagParameter(id=0x5e, data_class=CorusString)])
>> {0x5e: "FL_b0040"}
# Read multiple values
client.read_parameters(
    [
        IFlagParameter(id=0x5e, data_class=CorusString), 
        IFlagParameter(id=48, data_class=Index),
        IFlagParameter(id=49, data_class=Index)
    ]
)
>> {0x5e: "FL_b0040", 48: Decimal("234567.982"), 49: Decimal("222222.982")}

```

### Write parameters

```python
from iflag import CorusClient, TcpTransport
from iflag.data import Date
from iflag.parse import IFlagParameter
from datetime import datetime

transport = TcpTransport(address=('localhost', 4000))
client = CorusClient(transport=transport)
client.write_parameters([(IFlagParameter(id=106, data_class=Date), datetime.now())])

```

### Read database

```python
from iflag import CorusClient
from datetime import datetime, timedelta
client = CorusClient.with_tcp_transport(address=('localhost', 4000), database_layout=MY_DATABASE_LAYOUT)
client.read_database(database='interval', start=datetime.now(), stop=(datetime.now() - timedelta(hours=4)))
````

 - When reading databases you will need to know the `input_pulse_weight`. If it is not 
 set on the client at initiation or on the `read_database` call the client will read it 
 from the meter automatically.
