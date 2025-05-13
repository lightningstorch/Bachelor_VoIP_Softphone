import configparser
from pathlib import Path

"""
This module reads the configuration from the 'config.ini' file and
provides important parameters.
"""

_config = configparser.ConfigParser()
_config.read(Path(__file__).parent / 'config.ini')

server_ip = _config['network']['server_ip']
interface = _config['network']['interface']

database_type = _config['database']['type']
database_connection = _config['database']['connection_string']

captured_file_path = _config['captured_file']['file_path']


# RabbitMQ Message Service
rabbitmq_host = _config['rabbitmq']['host']
rabbitmq_port = int(_config['rabbitmq']['port'])
rabbitmq_user = _config['rabbitmq']['user']
rabbitmq_password = _config['rabbitmq']['password']
