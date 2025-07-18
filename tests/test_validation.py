import os

from utils.validation import validate_file, call_match
from my_logging.log_config import app_logger
from unittest.mock import patch

#==================================================
#               validate_file Tests
#==================================================

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

#==================================================
#               call_match Tests
#==================================================

def test_call_match_equal():
    from datetime import datetime

    participants = [
        DummyParticipant("user1", "192.168.0.1", 5000, "opus", "10.0.0.1", 10000),
        DummyParticipant("user2", "192.168.0.2", 5002, "opus", "10.0.0.2", 10002)
    ]

    buffer_call = DummyCall("caller1", datetime(2024, 1, 1, 12, 0, 0), participants)
    db_call     = DummyCall("caller1", datetime(2024, 1, 1, 12, 0, 0), participants.copy())

    assert call_match(buffer_call, db_call) is True

def test_call_match_unequal():
    from datetime import datetime

    participants_buffer = [
        DummyParticipant("user1", "192.168.0.1", 5000, "opus", "192.168.0.100", 10000),
        DummyParticipant("user2", "192.168.0.2", 5002, "opus", "192.168.0.200", 10002)
    ]
    participants_db = [
        DummyParticipant("user1", "192.168.0.1", 5000, "opus", "192.168.0.100", 10000),
        DummyParticipant("user2", "192.168.0.2", 9999, "opus", "192.168.0.200", 10002)  # port mismatch
    ]

    buffer_call = DummyCall("caller1", datetime(2024, 1, 1, 12, 0, 0), participants_buffer)
    db_call     = DummyCall("caller1", datetime(2024, 1, 1, 12, 0, 0), participants_db)

    assert call_match(buffer_call, db_call) is False


    buffer_call = DummyCall("Franz", datetime(2024, 1, 1, 12, 0, 0), participants_buffer)
    db_call = DummyCall("caller1", datetime(2024, 1, 1, 12, 0, 0), participants_db)

    assert call_match(buffer_call, db_call) is False

class DummyParticipant:
    def __init__(self, user, ip_address, media_port, mime_type, server_ip, server_port):
        self.user = user
        self.ip_address = ip_address
        self.media_port = media_port
        self.mime_type = mime_type
        self.server_ip = server_ip
        self.server_port = server_port

class DummyCall:
    def __init__(self, caller, start_time, participants):
        self.caller = caller
        self.start_time = start_time
        self.participants = participants