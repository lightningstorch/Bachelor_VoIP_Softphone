import unittest

from unittest.mock import Mock, patch
from queue import Queue
from call_context.manager_call_context import ManagerCallContext
from call_context.call_context import CallContext
from datastructure.async_message_service import AsyncMessageService


class TestManagerCallContext(unittest.TestCase):
    def setUp(self):
        self.mock_message_service = Mock(spec=AsyncMessageService)
        self.cleanup_queue = Queue()
        self.manager = ManagerCallContext(self.mock_message_service, self.cleanup_queue)

    def test_initialize_manager(self):
        """Test the initialization of the ManagerCallContext."""
        self.assertEqual(self.manager.all_contexts, {})
        self.assertEqual(dict(self.manager._known_ssrc), {})
        self.assertEqual(self.manager.message_service, self.mock_message_service)
        self.assertEqual(self.manager.cleanup_queue, self.cleanup_queue)

    def test_get_call_context_existing(self):
        """Test retrieving an existing call context by call_id."""
        call_id = "test_call"
        mock_call_context = Mock(spec=CallContext, call_id=call_id)
        self.manager.all_contexts[call_id] = mock_call_context

        result = self.manager.get_call_context(call_id)
        self.assertEqual(result, mock_call_context)

    @patch("call_context.manager_call_context.app_logger")
    def test_get_call_context_non_existing(self, mock_app_logger):
        """Test retrieving a non-existing call context."""
        call_id = "non_existing_call"
        result = self.manager.get_call_context(call_id)
        self.assertIsNone(result)
        mock_app_logger.debug.assert_called_once_with(f"Call ID '{call_id}' not found.")

    @patch("call_context.manager_call_context.CallContext")
    def test_create_or_insert_call_context_all(self, mock_call_context_class):
        """Test creating a new call context."""
        call_id = "new_call"

        mock_call_context = Mock()
        mock_call_context_class.return_value = mock_call_context

        result = self.manager.create_or_insert_call_context(call_id)
        mock_call_context_class.assert_called_once_with(call_id, self.mock_message_service)

        self.assertEqual(result, mock_call_context)
        self.assertEqual(self.manager.all_contexts[call_id], mock_call_context)

    @patch("call_context.manager_call_context.CallContext")
    def test_create_or_insert_call_context_with_ssrc_sample_rate(self, mock_call_context_class):

        call_id = "existing_call"
        ssrc = "12345"
        sample_rate = 48000
        mock_call_context = Mock(spec=CallContext)
        mock_call_context_class.return_value = mock_call_context

        result = self.manager.create_or_insert_call_context(call_id, ssrc, sample_rate)

        mock_call_context.set_sample_rate.assert_called_once_with(sample_rate)
        mock_call_context.insert_ssrc.assert_called_once_with(ssrc)
        self.assertIn(ssrc, self.manager._known_ssrc[call_id])
        self.assertEqual(result, mock_call_context)
        self.assertEqual(self.manager.all_contexts[call_id], mock_call_context)

    @patch("call_context.manager_call_context.CallContext")
    def test_create_or_insert_call_context_dupl_ssrc(self, mock_call_context_class):
        """Test inserting SSRC into an existing call context."""
        call_id = "existing_call"
        ssrc = "12345"

        mock_call_context = Mock(spec=CallContext)
        mock_call_context_class.result_value = mock_call_context

        self.manager.all_contexts[call_id] = mock_call_context
        self.manager._known_ssrc[call_id].add(ssrc)

        result = self.manager.create_or_insert_call_context(call_id, ssrc)

        mock_call_context.insert_ssrc.assert_not_called()
        mock_call_context.set_sample_rate.assert_not_called()

        self.assertEqual(result, self.manager.all_contexts[call_id])

    @patch("call_context.manager_call_context.CallContext")
    def test_enqueue_packet(self, mock_call_context_class):
        """Test enqueuing a packet to a call context."""
        call_id = "test_call"
        ssrc = "12345"
        packet = Mock()

        mock_call_context = Mock(spec=CallContext)
        mock_call_context_class.return_value = mock_call_context

        self.manager.enqueue_packet(call_id, ssrc, packet)
        mock_call_context.enqueue_packet.assert_called_once_with(ssrc, packet)

    @patch("call_context.manager_call_context.CallContext")
    def test_end_call_existing(self, mock_call_context_class):
        """Test ending an existing call."""
        call_id = "test_call"
        mock_call_context = Mock(spec=CallContext)
        mock_call_context_class.return_value = mock_call_context

        self.manager.all_contexts[call_id] = mock_call_context
        self.manager.end_call(call_id)

        mock_call_context.stop.assert_called_once()
        self.assertNotIn(call_id, self.manager.all_contexts)
        self.assertIn(call_id, self.manager.cleanup_queue.queue)

    @patch("call_context.manager_call_context.app_logger")
    def test_end_call_non_existing(self, mock_app_logger):
        """Test ending a non-existing call."""
        call_id = "non_existing_call"
        self.manager.end_call(call_id)

        self.assertNotIn(call_id, self.manager.all_contexts)
        self.assertNotIn(call_id, self.manager.cleanup_queue.queue)
        mock_app_logger.debug.assert_called_once_with(f"Call ID '{call_id}' not found for ending the call.")

    @patch("call_context.manager_call_context.CallContext")
    @patch("call_context.manager_call_context.app_logger")
    def test_shutdown_all_calls(self, mock_app_logger, mock_call_context_class):
        """Test shutting down all calls."""
        call_ids = ["call1", "call2", "call3", "call4"]
        mock_contexts = {call_id: Mock(spec=CallContext) for call_id in call_ids}
        self.manager.all_contexts = mock_contexts.copy()

        self.manager.shutdown_all_calls()

        for mock_context in mock_contexts.values():
            mock_context.stop.assert_called_once()
        self.assertEqual(self.manager.all_contexts, {})

    def test_thread_safety(self):
        """Test thread safety of the ManagerCallContext."""
        with patch.object(self.manager, 'lock') as mock_lock:
            self.manager.create_or_insert_call_context("test_call_id")
            mock_lock.__enter__.assert_called_once()
            mock_lock.__exit__.assert_called_once()









