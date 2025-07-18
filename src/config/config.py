import configparser
import os
from pathlib import Path

"""
This module reads the configuration from the 'config.ini' file and
provides important parameters.
"""


cfg_in_cwd = Path.cwd() / 'config.ini'
if cfg_in_cwd.exists():
    cfg_file = cfg_in_cwd
else:
    cfg_file = Path(__file__).parent / 'config.ini'

_config = configparser.ConfigParser()
_config.read(cfg_file)

if cfg_file == cfg_in_cwd:
    base_dir = cfg_file.parent
else:
    base_dir = Path(__file__).resolve().parents[2]

server_ip = _config['network']['server_ip']
interface = _config['network']['interface']

database_type = _config['database']['type']
database_connection = os.environ.get(
    "DATABASE_CONNECTION",
    _config['database']['connection_string']
)

_cf = _config['captured_file']
fp = Path(_cf['file_path'])
if _cf.get('path', '').lower() == 'relative' and not fp.is_absolute():
    captured_file_path = (base_dir / fp).resolve()
else:
    captured_file_path = fp.resolve()


# ===========================================
#           RabbitMQ Message Service
# ===========================================
rabbitmq_host = _config['rabbitmq']['host']
rabbitmq_port = int(_config['rabbitmq']['port'])
rabbitmq_user = _config['rabbitmq']['user']
rabbitmq_password = _config['rabbitmq']['password']

# ===========================================
#               Audio processing
# ===========================================
default_audio_sample_rate = int(_config['audio_processing']['default_sample_rate'])
audio_min_speech_duration = float(_config['audio_processing']['min_speech_duration'])
audio_gap_threshold = float(_config['audio_processing']['gap_threshold'])
audio_allowed_gaps = float(_config['audio_processing']['allowed_gaps'])

# vad
vad_mode = int(_config['audio_processing']['vad_mode'])

# noise reduction
noise_percentile = float(_config['audio_processing']['noise_percentile'])
noise_multiplier = float(_config['audio_processing']['noise_multiplier'])

# bandpass filter settings
bandpass_min_frequency = float(_config['audio_processing']['bandpass_min_frequency'])
bandpass_max_frequency = float(_config['audio_processing']['bandpass_max_frequency'])
bandpass_order = int(_config['audio_processing']['bandpass_order'])

# ===========================================
#           Logging Configuration
# ===========================================
app_log_level = _config['logging']['app_log_level']
message_service_log_level = _config['logging']['message_service_log_level']
aggregator_log_level = _config['logging']['aggregator_log_level']
call_context_log_level = _config['logging']['call_context_log_level']
database_log_level = _config['logging']['database_log_level']

# ===========================================
#        Authentication Configuration
# ===========================================
secret_key = _config['authentication']['secret_key']
algorithm = _config['authentication']['algorithm']
access_token_expire_minutes = int(_config['authentication']['access_token_expire_minutes'])

# ===========================================
#           Admin Configuration
# ===========================================
admin_username = _config['admin']['username']
admin_password = _config['admin']['password']


