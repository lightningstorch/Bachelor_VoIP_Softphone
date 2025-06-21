import importlib
import shutil
import sys
from pathlib import Path
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

    assert config.audio_sample_rate == 16000
    assert config.audio_min_speech_duration == 0.5
    assert config.audio_gap_threshold == 0.1
    assert config.audio_allowed_gaps == 0.05
    assert config.vad_mode == 3
    assert config.noise_percentile == 0.1
    assert config.noise_multiplier == 1.0
    assert config.bandpass_min_frequency == 300
    assert config.bandpass_max_frequency == 3400
    assert config.bandpass_order == 5


@pytest.mark.parametrize("ini_fixture, expected_order, expected_mode", [
    ("config_absolute.ini", 4, 'absolute'),
    ("config_relative.ini", 5, 'relative'),
])
def test_config_various(tmp_path, monkeypatch, ini_fixture, expected_order, expected_mode):
    # load the fixture from the fixtures directory to the temporary path
    src = Path(__file__).parent/"fixtures"/ini_fixture
    shutil.copy(src, tmp_path/"config.ini")

    import src.config.config as config
    importlib.reload(config)

    # create the relative path if needed
    if expected_mode == 'relative':
        (tmp_path/"data").mkdir()
        (tmp_path/"data"/"file.wav").write_bytes(b"")

    assert config.bandpass_order == expected_order
    if expected_mode == 'absolute':
        expected_path = Path("C:/foo/bar.wav").resolve()
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






