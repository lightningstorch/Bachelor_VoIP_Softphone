from unittest.mock import Mock

import pytest
from call_context.call_context import CallContext


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