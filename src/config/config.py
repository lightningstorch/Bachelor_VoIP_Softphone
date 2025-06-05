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

if _config['captured_file']['path'] == 'relative':
    captured_file_path_relativ = _config['captured_file']['file_path']

    project_root = Path(__file__).resolve().parents[2]
    captured_file_path = (project_root / captured_file_path_relativ).resolve()
else:
    captured_file_path = _config['captured_file']['file_path']


# RabbitMQ Message Service
rabbitmq_host = _config['rabbitmq']['host']
rabbitmq_port = int(_config['rabbitmq']['port'])
rabbitmq_user = _config['rabbitmq']['user']
rabbitmq_password = _config['rabbitmq']['password']
