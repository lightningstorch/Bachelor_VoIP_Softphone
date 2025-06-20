import json
import threading
import pytest

from unittest.mock import Mock
from call_context import call_context
from call_context.call_context import CallContext

"""
Tests for the CallContext class in the call_context module.
These tests cover the functionality of inserting SSRCs, calculating overlapping intervals,
sending intervals, and handling audio packet buffering and analysis.
"""

def test_calculate_overlapping_intervals():
    fake_service = Mock()
    # Create a CallContext instance
    ctx = CallContext(call_id="test_call", message_service=fake_service)

    # Insert SSRCs
    ctx.insert_ssrc("ssrc1")
    ctx.insert_ssrc("ssrc2")

    # Manually add intervals for testing
    ctx.intervals["ssrc1"] = [(0, 5), (10, 17), (20, 25), (30, 35), (40, 48)]
    ctx.intervals["ssrc2"] = [(3, 8), (12, 17), (17, 23), (28, 38), (42, 45)]

    captured_overlays = []
    def fake_send(*, speech_intervals, ssrc=None, type_interval="overlap"):
        captured_overlays.extend(speech_intervals)
    ctx._send_intervals = fake_send

    # Calculate overlapping intervals
    ctx.calculate_overlapping_intervals()

    # Check if the overlaps are calculated correctly
    expected_overlaps = [(3, 5), (12, 17), (20, 23), (30, 35), (42, 45)]
    assert captured_overlays == expected_overlaps, f"Expected {expected_overlaps}, got {captured_overlays}"

def test_send_intervals():
    fake_service = Mock()
    ctx = CallContext.__new__(CallContext)
    ctx.call_id = "callXYZ"
    ctx.message_service = fake_service
    ctx._store_intervals = {}

    # Test sending intervals with a specific SSRC
    intervals = [(0, 5), (10, 17)]
    ctx._send_intervals(speech_intervals=intervals, ssrc="ssrc1")

    assert fake_service.publish.call_count == 2

    for ((args, kwargs), (start, end)) in zip(fake_service.send.call_args_list, intervals):
        payload = json.loads(kwargs["payload"])
        assert payload["call_id"] == "callXYZ"
        assert payload["ssrc"] == "ssrc1"
        assert payload["type"] == "speech"
        assert payload["start"] == start
        assert payload["end"] == end

def test_enqueue_packet_and_logging(monkeypatch):
    fake_service = Mock()
    fake_logger = Mock()
    dummy_packet = object()

    monkeypatch.setattr(call_context, "app_logger", fake_logger)

    ctx = CallContext(call_id="callXYZ", message_service=fake_service)

    ctx.insert_ssrc("ssrc1")
    ctx.enqueue_packet("ssrc1", dummy_packet)

    got = ctx._queues["ssrc1"].get_nowait()
    assert got is dummy_packet

    ctx.enqueue_packet("ssrc2", dummy_packet)
    fake_logger.warning.assert_called_once_with("SSRC 'ssrc2' not found in call context 'callXYZ'.")

def test_flash_buffers_with_data_and_final_interval(flush_context):
    ctx, fake_buffer, fake_analyser, calls = flush_context

    fake_buffer.flush.return_value = ["pktA", "pktB"]
    fake_analyser.analyze_audio.return_value = [(10, 20), (30, 40)]
    fake_analyser.close.return_value = (50, 60)

    ctx._flush_buffers()

    fake_buffer.flush.assert_called_once_with()
    fake_analyser.analyze_audio.assert_called_once_with(["pktA", "pktB"])

    assert calls[0] == ("ssrc1", [(10, 20), (30, 40)], None)
    assert calls[1] == ("ssrc1", (50, 60), "Final speech interval")

def test_flush_buffers_without_data(flush_context):
    ctx, fake_buffer, fake_analyser, calls = flush_context

    fake_buffer.flush.return_value = []
    fake_analyser.analyze_audio.return_value = [(10, 20), (30, 40)]
    fake_analyser.close.return_value = None

    ctx._flush_buffers()

    fake_buffer.flush.assert_called_once_with()
    fake_analyser.analyze_audio.assert_not_called()
    fake_analyser.close.assert_called_once_with()

    assert not calls, "No intervals should be handled when no data is present."

# ================================================
#           Helper methods
# ================================================

@pytest.fixture
def flush_context(monkeypatch):
    """
    Fixture to create a CallContext with mocked dependencies for testing buffer flushing and interval handling.
    This fixture sets up a CallContext with a mocked message service, buffer, and analyzer.
    It also overrides the threading.Thread.start method to prevent actual thread execution during tests.
    This allows for controlled testing of the buffer flushing and interval handling logic without side effects.
    """
    monkeypatch.setattr(threading.Thread, "start", lambda self: None)

    fake_service = Mock()
    fake_buffer = Mock()
    fake_analyser = Mock()

    ctx = CallContext(call_id="callXYZ", message_service=fake_service)
    ctx.insert_ssrc("ssrc1")
    ctx._buffers = {"ssrc1": fake_buffer}
    ctx._analysers = {"ssrc1": fake_analyser}

    calls = []
    def fake_handle(ssrc, intervals, label=None):
        calls.append((ssrc, intervals, label))
    ctx._handle_intervals = fake_handle

    return ctx, fake_buffer, fake_analyser, calls

