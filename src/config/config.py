import configparser
from pathlib import Path


_config = configparser.ConfigParser()
_config.read(Path(__file__).parent / 'config.ini')

server_ip = _config['network']['server_ip']
interface = _config['network']['interface']

