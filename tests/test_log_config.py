import asyncio
import unittest
from unittest.mock import Mock

from my_logging import log_config


class TestLogConfigSSE(unittest.TestCase):
    def setUp(self):
        log_config._sse_loop = None
        log_config.event_queue = asyncio.Queue()

    def tearDown(self):
        log_config._sse_loop = None

    def test_set_event_loop(self):
        """Test setting the global asyncio event loop for Server-Sent Events (SSE)."""
        mock_loop = Mock(spec=asyncio.AbstractEventLoop)
        log_config.set_event_loop(mock_loop)
        self.assertEqual(log_config._sse_loop, mock_loop)

    def test_set_event_loop_multiple_times(self):
        """Test setting the event loop multiple times."""
        mock_loop1 = Mock(spec=asyncio.AbstractEventLoop)
        mock_loop2 = Mock(spec=asyncio.AbstractEventLoop)

        log_config.set_event_loop(mock_loop1)
        self.assertEqual(log_config._sse_loop, mock_loop1)

        # Setting a new loop should not change the existing one
        log_config.set_event_loop(mock_loop2)
        self.assertEqual(log_config._sse_loop, mock_loop1)

    def test_broadcast_log_with_sse_loop(self):
        """Test broadcasting a log event when the SSE event loop is set."""
        mock_loop = Mock(spec=asyncio.AbstractEventLoop)

        def mock_call_soon_threadsafe(callback, *args):
            # Simulate the callback being called with the provided arguments
            callback(*args)

        mock_loop.call_soon_threadsafe.side_effect = mock_call_soon_threadsafe

        def mock_create_task(coro):
            coro.close()
            return Mock()

        mock_loop.create_task.side_effect = mock_create_task
        log_config.set_event_loop(mock_loop)

        event_type = "test_event"
        payload = "test_payload"

        log_config.broadcast_log(event_type, payload)

        # verify that call_soon_threadsafe was called
        mock_loop.call_soon_threadsafe.assert_called_once()

        # Verify that create_task was called
        mock_loop.create_task.assert_called_once()

        # Verify that the event was put into the queue
        call_args = mock_loop.call_soon_threadsafe.call_args[0]
        callback = call_args[0]
        self.assertEqual(callback, mock_loop.create_task)
