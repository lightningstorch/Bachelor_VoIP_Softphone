import importlib
import re
import shutil
import sys
from pathlib import Path
from site import abs_paths

import pytest

def test_full_config_loading():
    import src.config.config as config
    importlib.reload(config)

    assert config.server_ip == '127.0.0.1'
    assert config.interface == 'eth0'

    assert config.database_type == 'sqlite'
    assert config.database_connection == 'db.sqlite3'

    assert config.captured_file_path == (Path.cwd() / 'data/file.wav').resolve()

    assert config.rabbitmq_host == 'localhost'
    assert config.rabbitmq_port == 5672
    assert config.rabbitmq_user == 'guest'
    assert config.rabbitmq_password == 'guest'

    assert config.default_audio_sample_rate == 16000
    assert config.audio_min_speech_duration == 0.5
    assert config.audio_gap_threshold == 0.1
    assert config.audio_allowed_gaps == 0.05
    assert config.vad_mode == 3
    assert config.noise_percentile == 0.1
    assert config.noise_multiplier == 1.0
    assert config.bandpass_min_frequency == 300
    assert config.bandpass_max_frequency == 3400
    assert config.bandpass_order == 5

    assert config.secret_key == '123456789'
    assert config.algorithm == 'HS256'
    assert config.access_token_expire_minutes == 30

    assert config.admin_username == 'admin'
    assert config.admin_password == 'admin'


@pytest.mark.parametrize("ini_fixture, expected_order, expected_mode", [
    ("config_absolute.ini", 4, 'absolute'),
    ("config_relative.ini", 5, 'relative'),
])
def test_config_various(tmp_path, monkeypatch, ini_fixture, expected_order, expected_mode):
    # load the fixture from the fixtures directory to the temporary path
    src = Path(__file__).parent/"fixtures"/ini_fixture
    ini_text = src.read_text()

    abs_file = None
    if expected_mode == 'absolute':
        # create a file in the temp_path
        abs_file = tmp_path / "test" / "file.wav"
        abs_file.parent.mkdir(parents=True, exist_ok=True)
        abs_file.write_bytes(b"")
        # change the ini path to the absolute path
        ini_text = re.sub(
            r"file_path\s*=\s*.+",
            lambda m: f"file_path = {abs_file}",
            ini_text
        )
    elif expected_mode == 'relative':
        (tmp_path/"data").mkdir()
        (tmp_path/"data"/"file.wav").write_bytes(b"")

    # write the adapted config to the temporary path
    ini_dest = tmp_path / "config.ini"
    ini_dest.write_text(ini_text)

    monkeypatch.chdir(tmp_path)
    sys.modules.pop("src.config.config", None)
    import src.config.config as config
    importlib.reload(config)

    assert config.bandpass_order == expected_order

    if expected_mode == 'absolute':
        expected_path = abs_file.resolve()
    else:
        expected_path = (tmp_path/"data"/"file.wav").resolve()

    assert config.captured_file_path == expected_path

# ================================================
#           Helper methods
# ================================================

@pytest.fixture(autouse=True)
def use_test_config(tmp_path, monkeypatch):
    src = Path(__file__).parent / "fixtures" / "config.ini"
    dst = tmp_path / "config.ini"
    shutil.copy(src, dst)

    # Change the current working directory to the temporary path
    monkeypatch.chdir(tmp_path)

    # Ensure the config module is reloaded to use the test config
    sys.modules.pop("src.config.config", None)
    yield






