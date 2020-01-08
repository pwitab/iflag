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

- Good to know: There are several different float formats due to memory constraints in
    the protocol and device. All floats are handled as `decimal.Decimal` in Python to 
    not have float rounding errors.

### Read parameters:

```python

from iflag import CorusClient

client = CorusClient.with_tcp_transport(address=('localhost', 4000))
client.read_parameters(['datetime', 'index_unconverted', 'index_converted'])

```

### Write parameters

```python
from iflag import CorusClient, TcpTransport
from datetime import datetime
transport = TcpTransport(address=('localhost', 4000))
client = CorusClient(transport=transport)
client.write_parameters({'datetime': datetime.now()})

```

### Read database

```python
from iflag import CorusClient
from datetime import datetime, timedelta
client = CorusClient.with_tcp_transport(address=('localhost', 4000))
client.read_database(database='interval', start=datetime.now(), stop=(datetime.now() - timedelta(hours=4)))
```

## Parameters

Not all parameters available in a device have been mapped out yet. 
But the most important ones have been.

Parameter Name  | Parameter Description
--- | ---
firmware_version | Main firmware version 
pulse_weight | Input pulse weight 
compressibility_formula | Compressibility Formula: 0=AGANX19 Standard, 1=S-GERG88, 2=PT, 3=AGANx19 Modified, 4=Not Used, 5=T, 6=16 Coeff. 7=AGA8 
pressure_base | Base pressure, in selected pressure unit 
temperature_base | Base temperature, in Kelvin 
pressure_low | Low pressure threshold (Pmin) 
pressure_high | High pressure threshold (Pmax) 
temperature_low | Low temperature threshold (Tmin) 
temperature_high | High temperature threshold (Tmax) 
datetime | Current time and date 
battery_days | Battery Autonomy Counter, in days 
index_unconverted | Unconverted Index 
index_converted | Converted Index

