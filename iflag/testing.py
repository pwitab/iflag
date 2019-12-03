from iflag.client import CorusClient
import logging
from logging.config import DictConfigurator


logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "filters": {},
            "formatters": {
                "main_formatter": {
                    "format": "[{asctime}] :: [{levelname}] :: {name} :: {message}",
                    "style": "{",
                }
            },
            "handlers": {
                "console": {
                    "level": "DEBUG",
                    "filters": [],
                    "class": "logging.StreamHandler",
                    "formatter": "main_formatter",
                }
            },
            "loggers": {"": {"handlers": ["console"], "level": "DEBUG"}},
        }
    )

address = ('10.70.138.159', 8000)
client = CorusClient.with_tcp_transport(address=address)

client.connect()
#client.transport.recv(600)
client.wakeup()
client.sign_on()

client.read_database()
