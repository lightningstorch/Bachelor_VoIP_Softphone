import unittest
import json

from unittest.mock import MagicMock, patch
from datetime import datetime
from aio_pika import ExchangeType
from datastructure.aggregator import Aggregator
from datastructure.dataclass_models import CallInfo, ParticipantInfo, TalkingInterval


class TestAggregator(unittest.TestCase):
    def setUp(self):
        self.message_service = MagicMock()
        self.message_service.subscribe.return_value.result = MagicMock()
        self.aggregator = Aggregator(self.message_service)

    def test_init(self):
        """ Test the initialization of the Aggregator class """
        self.assertEqual(self.message_service.subscribe.call_count, 8)

        # Verify specific subscription calls
        self.message_service.subscribe.assert_any_call(
            self.aggregator.aggregator_new_call,
            "NEW_CALL",
            ExchangeType.DIRECT,
            "aggregator_new_call_queue",
            "new_call",
        )

    @patch("asyncio.create_task")
    def test_aggregator_new_call(self,  mock_create_task):
        """ Test the aggregator_new_call method to ensure it correctly processes new calls"""
        message = MagicMock()
        message.body.decode.return_value = json.dumps({
            "call_id": "call_123",
            "caller": "test_caller"
        })

        self.aggregator.aggregator_new_call(message)
        mock_create_task.assert_called_once_with(message.ack())

        self.assertIn("call_123", self.aggregator._call_buffer)
        self.assertEqual(self.aggregator._call_buffer["call_123"].caller, "test_caller")

    @patch("asyncio.create_task")
    @patch.object(Aggregator, "_store")
    def test_aggregator_participation(self, mock_store, mock_create_task):
        """ Test the aggregator_participation method to ensure it correctly adds a participant"""
        self.aggregator._call_buffer["call_123"] = CallInfo(caller="test_caller")

        message = MagicMock()
        message.body.decode.return_value = json.dumps({
            "call_id": "call_123",
            "user": "user_456",
            "ip_address": "192.168.1.1",
            "media_port": 12345,
            "mime_type": "opus"
        })

        self.aggregator.aggregator_participation(message)

        mock_create_task.assert_called_once_with(message.ack())

        participant = next(p for p in self.aggregator._call_buffer["call_123"].participants if p.user == "user_456")
        self.assertEqual(participant.ip_address, "192.168.1.1")
        self.assertEqual(participant.media_port, 12345)
        self.assertEqual(participant.mime_type, "opus")

        mock_store.assert_called_once_with("call_123")

    @patch("asyncio.create_task")
    @patch.object(Aggregator, "_store")
    def test_server_info(self, mock_store, mock_create_task):
        self.aggregator._call_buffer["call_123"] = CallInfo(caller="test_caller")

        message = MagicMock()
        message.body.decode.return_value = json.dumps({
            "call_id": "call_123",
            "server_ip": "192.168.1.1",
            "server_port": 8080,
            "user": "test_caller"
        })

        self.aggregator.aggregator_server_info(message)
        mock_create_task.assert_called_once_with(message.ack())

        participant = next(p for p in self.aggregator._call_buffer["call_123"].participants if p.user == "test_caller")
        self.assertEqual(participant.server_ip, "192.168.1.1")
        self.assertEqual(participant.server_port, 8080)

        mock_store.assert_called_once_with("call_123")

    @patch("asyncio.create_task")
    @patch.object(Aggregator, "_store")
    def test_aggregator_ack(self, mock_store, mock_create_task):
        self.aggregator._call_buffer["call_123"] = CallInfo(caller="test_caller")

        date_time = datetime.now().isoformat()
        message = MagicMock()
        message.body.decode.return_value = json.dumps({
            "call_id": "call_123",
            "start_time": date_time
        })

        self.aggregator.aggregator_ack(message)
        mock_create_task.assert_called_once_with(message.ack())

        call_info = self.aggregator._call_buffer["call_123"]

        self.assertEqual(call_info.start_time.isoformat(), date_time)
        self.assertTrue(call_info.ack_received)

        mock_store.assert_called_once_with("call_123")

    @patch("asyncio.create_task")
    @patch("datastructure.aggregator.store_call_end")
    def test_aggregator_call_end(self, mock_store_call_end, mock_create_task):
        self.aggregator._call_buffer["call_123"] = CallInfo(caller="test_caller")
        self.aggregator._call_buffer["call_123"].ack_received = True
        self.aggregator._call_buffer["call_123"].stored = True

        end_time = datetime.now().isoformat()
        message = MagicMock()
        message.body.decode.return_value = json.dumps({
            "call_id": "call_123",
            "end_time": end_time
        })

        self.aggregator.aggregator_call_end(message)
        mock_create_task.assert_called_once_with(message.ack())

        self.assertNotIn("call_123", self.aggregator._call_buffer)

        call_id, call_info = mock_store_call_end.call_args[0]

        mock_store_call_end.assert_called_once_with("call_123", call_info)

        self.assertEqual(call_id, "call_123")
        self.assertEqual(call_info.end_time.isoformat(), end_time)
        self.assertTrue(call_info.ack_received)
        self.assertTrue(call_info.stored)

    @patch("asyncio.create_task")
    def test_aggregator_call_decline(self, mock_create_task):
        """ Test the aggregator_call_decline method to ensure it correctly handles call declines """
        self.aggregator._call_buffer["call_123"] = CallInfo(caller="test_caller")

        message = MagicMock()
        message.body.decode.return_value = json.dumps({
            "call_id": "call_123"
        })

        self.aggregator.aggregator_call_decline(message)
        mock_create_task.assert_called_once_with(message.ack())

        self.assertNotIn("call_123", self.aggregator._call_buffer)

    @patch("asyncio.create_task")
    @patch("datastructure.aggregator.store_ssrc")
    def test_aggregator_ssrc(self, mock_store_ssrc, mock_create_task):
        """ Test the aggregator_store_ssrc method to ensure it correctly stores SSRC information """
        self.aggregator._call_buffer["call_123"] = CallInfo(caller="test_caller")
        self.aggregator._call_buffer["call_123"].stored = True
        self.aggregator._call_buffer["call_123"].participants.append(
            ParticipantInfo(user="user_456", ip_address="10.0.0.0", media_port=12345, mime_type="opus")
        )

        message = MagicMock()
        message.body.decode.return_value = json.dumps({
            "call_id": "call_123",
            "user": "user_456",
            "ssrc": "0x12345678"
        })

        self.aggregator.aggregator_ssrc(message)
        mock_create_task.assert_called_once_with(message.ack())

        participant = next(p for p in self.aggregator._call_buffer["call_123"].participants if p.user == "user_456")
        self.assertEqual(participant.ssrc, "0x12345678")

        mock_store_ssrc.assert_called_once_with("call_123", "0x12345678", "user_456")

        arg_call_id, arg_ssrc, arg_user = mock_store_ssrc.call_args[0]

        self.assertEqual(arg_call_id, "call_123")
        self.assertEqual(arg_ssrc, "0x12345678")
        self.assertEqual(arg_user, "user_456")

    @patch("asyncio.create_task")
    @patch("datastructure.aggregator.store_talking_sections")
    @patch.object(Aggregator, "_store")
    def test_aggregator_talking_section(self, mock_store, mock_store_talking_sections, mock_create_task):
        """ Test the aggregator_talking_section method to ensure it correctly stores talking sections """
        self.aggregator._call_buffer["call_123"] = CallInfo(caller="test_caller")
        self.aggregator._call_buffer["call_123"].stored = True
        self.aggregator._call_buffer["call_123"].participants.append(
            ParticipantInfo(user="user_456", ip_address="10.0.0.0", media_port=12345, mime_type="opus", ssrc="0x12345678")
        )

        talking_interval = TalkingInterval(
            type = "speech",
            call_id = "call_123",
            ssrc = "0x12345678",
            start = 0,
            end = 10,
        )

        message = MagicMock()
        message.body.decode.return_value = json.dumps({
            "type": "speech",
            "call_id": "call_123",
            "ssrc": "0x12345678",
            "start": 0,
            "end": 10,
        })

        self.aggregator.aggregator_talking_section(message)
        mock_create_task.assert_called_once_with(message.ack())

        mock_store.assert_not_called()
        mock_store_talking_sections.assert_called_once_with(talking_interval)

        arg_talking_interval = mock_store_talking_sections.call_args[0][0]

        self.assertEqual(arg_talking_interval.type, "speech")
        self.assertEqual(arg_talking_interval.call_id, "call_123")
        self.assertEqual(arg_talking_interval.ssrc, "0x12345678")
        self.assertEqual(arg_talking_interval.start, 0)
        self.assertEqual(arg_talking_interval.end, 10)


        # buffer details aren't stored yet
        mock_store_talking_sections.reset_mock()
        mock_store.reset_mock()
        mock_create_task.reset_mock()

        self.aggregator._call_buffer["call_123"].stored = False

        self.aggregator.aggregator_talking_section(message)

        mock_create_task.assert_called_once_with(message.ack())
        mock_store.assert_called_once_with("call_123")

        mock_store_talking_sections.assert_called_once_with(talking_interval)


    def test_get_participant(self):
        """ Test the get_participant method to ensure it retrieves the correct participant """
        self.aggregator._call_buffer["call_123"] = CallInfo(caller="test_caller")
        self.aggregator._call_buffer["call_123"].participants.append(
            ParticipantInfo(
                user="user_456",
                ip_address="10.0.0.0",
                media_port=12345,
                mime_type="opus",
                ssrc="0x12345678"
            )
        )

        body = {
            "call_id": "call_123",
            "user": "user_456"
        }

        participant = self.aggregator.get_participant(body)

        self.assertIsNotNone(participant)
        self.assertEqual(participant.user, "user_456")

    @patch("datastructure.aggregator.store_call_start")
    @patch("datastructure.aggregator.store_ssrc")
    def test_store(self, mock_store_ssrc, mock_store_call_start):
        """ Test the store method to ensure it correctly stores call information """
        call_id = "call_123"
        call_info = CallInfo(caller="test_caller")
        self.aggregator._call_buffer[call_id] = call_info
        self.aggregator._call_buffer[call_id].ack_received = True
        self.aggregator._call_buffer[call_id].participants.append(
            ParticipantInfo(
                user="user_456",
                ip_address="10.0.0.0",
                media_port=12345,
                mime_type="opus",
                server_ip="1.1.1.1",
                server_port=12345,
                ssrc="0x12345678"
            )
        )

        self.aggregator._store(call_id)

        mock_store_call_start.assert_called_once_with(call_id, call_info)
        mock_store_ssrc.assert_called_once_with("call_123", "0x12345678", "user_456")

        self.assertTrue(self.aggregator._call_buffer[call_id].stored)




