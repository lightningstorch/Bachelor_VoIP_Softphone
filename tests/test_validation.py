import os

from utils.validation import validate_file
from my_logging.log_config import app_logger
from unittest.mock import patch

def test_validate_file_nonexistent(tmp_path):
    fp = tmp_path / "not_existing.pcap"
    assert not fp.exists()

    with patch.object(app_logger, 'error') as mock_error:
        assert validate_file(fp) is False

        # Check that the error message was logged correctly
        mock_error.assert_called_once_with(f"File {fp} does not exist or is not readable")

def test_validate_file_bad_extension(tmp_path):
    fp = tmp_path / "not_existing.txt"
    fp.write_text("This is a test file.")
    assert fp.exists()

    with patch.object(app_logger, 'error') as mock_error:
        assert validate_file(fp) is False

        # Check that the error message was logged correctly
        mock_error.assert_called_once_with(f"File extension must be one of ['.pcap', '.pcapng'] and not .txt")

def test_allowed_file_extensions(tmp_path):
    for ext in ['.pcap', '.pcapng', '.PCAP', '.PcapNg', '.PCAPNG']:
        fp = tmp_path / f"test{ext}"
        fp.write_bytes(b"x")
        assert fp.exists()

        with patch.object(app_logger, 'debug') as mock_debug, \
             patch.object(app_logger, 'error') as mock_error:

            assert validate_file(fp) is True

            # Check that debug messages were logged correctly
            mock_debug.assert_any_call(f"File is valid: {fp}")

            # Ensure no error messages were logged
            mock_error.assert_not_called()

def test_validate_file_permission_denied(tmp_path, monkeypatch):
    fp = tmp_path / "test.pcap"
    fp.write_bytes(b"This is a test file.")
    assert fp.exists()

    # Simulate permission denied by patching os.path.isfile and os.access
    monkeypatch.setattr(os.path, 'isfile', lambda path: True)
    monkeypatch.setattr(os, 'access', lambda path, mode: False)

    with patch.object(app_logger, 'error') as mock_error:
        assert validate_file(fp) is False

        # Check that the error message was logged correctly
        mock_error.assert_called_once_with(f"File {fp} does not exist or is not readable")