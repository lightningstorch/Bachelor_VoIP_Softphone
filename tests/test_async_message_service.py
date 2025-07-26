import time
import unittest
import asyncio
from unittest.mock import AsyncMock, patch

from aio_pika.exchange import ExchangeType
from datastructure.async_message_service import AsyncMessageService


class TestAsyncMessageService(unittest.TestCase):

    def setUp(self):
        AsyncMessageService._instance = None

    def tearDown(self):
        AsyncMessageService._instance = None

    @patch("datastructure.async_message_service.aio_pika.connect_robust")
    def test_singleton_instance(self, mock_connect):
        """Test that AsyncMessageService is a singleton and returns the same instance"""
        mock_connection = AsyncMock()
        mock_connect.return_value = mock_connection

        service1 = AsyncMessageService()
        service2 = AsyncMessageService()

        self.assertIs(service1, service2)

    @patch("datastructure.async_message_service.aio_pika.connect_robust")
    def test_get_message_service_function(self, mock_connect):
        """Test that get_message_service returns the singleton instance"""
        mock_connection = AsyncMock()
        mock_connect.return_value = mock_connection

        service1 = AsyncMessageService()
        service2 = AsyncMessageService()

        self.assertIs(service1, service2)
        self.assertIsInstance(service1, AsyncMessageService)

    @patch("datastructure.async_message_service.aio_pika.connect_robust")
    def test_connection_retry(self, mock_connect):
        """Test that connection retries are handled correctly"""
        mock_connection = AsyncMock()
        mock_connect.side_effect = [
            Exception("Connection refused"),
            Exception("Still failing"),
            mock_connection  # Simulate a successful connection on the third attempt
        ]

        service = AsyncMessageService()

        # Verify connection was eventually established
        self.assertEqual(mock_connect.call_count, 3)

        service.close()

    @patch("datastructure.async_message_service.aio_pika.connect_robust")
    def test_connection_max_retries_exceeded(self, mock_connect):
        """Test that an exception is raised when max connection retries are exceeded"""
        mock_connect.side_effect = Exception("Connection refused")

        with self.assertRaises(ConnectionError) as context:
            AsyncMessageService()

        self.assertIn("Could not connect to RabbitMQ", str(context.exception))
        self.assertEqual(mock_connect.call_count, 3)


#==========================================================================

class TestAsyncMessageServiceWithMockedConnection(unittest.TestCase):

    def setUp(self):
        AsyncMessageService._instance = None

        self.mock_connection = AsyncMock()
        self.mock_channel = AsyncMock()
        self.mock_exchange = AsyncMock()
        self.mock_queue = AsyncMock()
        self.mock_message = AsyncMock()

        self.mock_connection.channel.return_value = self.mock_channel
        self.mock_channel.declare_exchange.return_value = self.mock_exchange
        self.mock_channel.declare_queue.return_value = self.mock_queue
        self.mock_queue.consume.return_value = "consume_tag"

    def tearDown(self):
        AsyncMessageService._instance = None

    @patch('datastructure.async_message_service.aio_pika.connect_robust')
    @patch('datastructure.async_message_service.aio_pika.Message')
    def test_publish_success(self, mock_message_class, mock_connect):
        """Test that messages can be published successfully"""
        mock_connect.return_value = self.mock_connection
        mock_message_class.return_value = self.mock_message

        service = AsyncMessageService()

        test_message = "publish_success"

        service.publish(
            test_message,
            "test_exchange_name",
            ExchangeType.DIRECT,
            "test_routing_key",
        )

        time.sleep(0.5)

        mock_connect.assert_called_once()
        mock_message_class.assert_called_with(test_message.encode())
        self.mock_exchange.publish.assert_called_once()

        service.close()

    @patch('datastructure.async_message_service.aio_pika.connect_robust')
    @patch('datastructure.async_message_service.aio_pika.Message')
    def test_publish_async_success(self, mock_message_class, mock_connect):
        """Test that messages can be published asynchronously"""
        mock_connect.return_value = self.mock_connection
        mock_message_class.return_value = self.mock_message

        service = AsyncMessageService()

        test_message = "publish_success"

        future = asyncio.run_coroutine_threadsafe(
            service.publish_async(
                test_message,
                "test_exchange_name",
                ExchangeType.DIRECT,
                "test_routing_key"
            ),
            service.loop
        )

        time.sleep(0.5)

        mock_connect.assert_called_once()
        mock_message_class.assert_called_with(test_message.encode())
        self.mock_exchange.publish.assert_called_once()

        service.close()

    @patch('datastructure.async_message_service.aio_pika.connect_robust')
    def test_publish_with_retry(self, mock_connect):
        """Test that message publishing retries on failure"""
        self.mock_exchange.publish.side_effect = [
            Exception("Connection lost"),
            Exception("Still failing"),
            None  # Success on the third attempt
        ]

        service = AsyncMessageService()


        service.publish(
            "test_message",
            "test_exchange_name",
            ExchangeType.DIRECT,
            "test_routing_key"
        )

        mock_connect.assert_called_once()
        service.close()

    @patch('datastructure.async_message_service.aio_pika.connect_robust')
    @patch('datastructure.async_message_service.message_service_logger')
    def test_publish_failure(self, mock_logger, mock_connect):
        """Test that an error is logged when message publishing fails after retries"""
        mock_connect.return_value = self.mock_connection

        self.mock_exchange.publish.side_effect = Exception("Connection lost")

        service = AsyncMessageService()

        service._publishers["test_exchange_name"] = (self.mock_channel, self.mock_exchange)

        service.publish(
            "test_message",
            "test_exchange_name",
            ExchangeType.DIRECT,
            "test_routing_key"
        )
        time.sleep(0.5)

        self.assertGreaterEqual(mock_logger.error.call_count, 6)

        messages = [call.args[0] for call in mock_logger.error.call_args_list]
        self.assertIn("Could not publish message to exchange test_exchange_name after 5 attempts", messages)
        self.assertTrue(any("Error while publishing message to exchange test_exchange_name" in msg for msg in messages))

        service.close()

    @patch('datastructure.async_message_service.aio_pika.connect_robust')
    def test_subscribe_success(self, mock_connect):
        """Test that messages can be subscribed to successfully"""
        mock_connect.return_value = self.mock_connection

        service = AsyncMessageService()

        def _test_callback(message):
            pass

        service.subscribe(
            _test_callback,
            "test_exchange_name",
            ExchangeType.DIRECT,
            "test_queue",
            "test_routing_key",
        )

        time.sleep(0.5)

        self.mock_connection.channel.assert_called()
        self.mock_channel.set_qos.assert_called_with(prefetch_count=2)
        self.mock_channel.declare_exchange.assert_called_with(
            "test_exchange_name", ExchangeType.DIRECT, durable=True
        )
        self.mock_channel.declare_queue.assert_called_with(
            "test_queue", durable=True
        )
        self.mock_queue.bind.assert_called_with(
            "test_exchange_name", routing_key="test_routing_key"
        )
        self.mock_queue.consume.assert_called_with(_test_callback)

        service.close()

    @patch('datastructure.async_message_service.aio_pika.connect_robust')
    def test_subscribe_async_success(self, mock_connect):
        """Test that messages can be subscribed to asynchronously"""
        mock_connect.return_value = self.mock_connection

        service = AsyncMessageService()

        def _test_callback(message):
            pass

        asyncio.run_coroutine_threadsafe(
            service.subscribe_async(
                _test_callback,
                "test_exchange_name",
                ExchangeType.DIRECT,
                "test_queue",
                "test_routing_key",
            ),
            service.loop
        )

        time.sleep(0.5)

        self.mock_connection.channel.assert_called()
        self.mock_channel.set_qos.assert_called_with(prefetch_count=2)
        self.mock_channel.declare_exchange.assert_called_with(
            "test_exchange_name", ExchangeType.DIRECT, durable=True
        )
        self.mock_channel.declare_queue.assert_called_with(
            "test_queue", durable=True
        )
        self.mock_queue.bind.assert_called_with(
            "test_exchange_name", routing_key="test_routing_key"
        )
        self.mock_queue.consume.assert_called_with(_test_callback)

        service.close()

    @patch('datastructure.async_message_service.aio_pika.connect_robust')
    def test_subscribe_with_retry(self, mock_connect):
        """Test that subscription retries on failure"""
        mock_connect.return_value = self.mock_connection

        self.mock_exchange.subscribe.side_effect = [
            Exception("Connection lost"),
            Exception("Still failing"),
            None  # Success on the third attempt
        ]

        service = AsyncMessageService()

        def _test_callback(message):
            pass

        service.subscribe(
            _test_callback,
            "test_exchange_name",
            ExchangeType.DIRECT,
            "test_queue",
            "test_routing_key",
        )

        time.sleep(0.5)

        mock_connect.assert_called_once()
        service.close()

    @patch('datastructure.async_message_service.aio_pika.connect_robust')
    @patch('datastructure.async_message_service.message_service_logger')
    def test_subscribe_failed(self, mock_logger, mock_connect):
        """Test that an error is logged when subscription fails after retries"""
        mock_connect.return_value = self.mock_connection

        self.mock_queue.consume.side_effect = Exception("Connection lost")

        service = AsyncMessageService()

        def _test_callback(message):
            pass

        service.subscribe(
            _test_callback,
            "test_exchange_name",
            ExchangeType.DIRECT,
            "test_queue",
            "test_routing_key",
        )

        time.sleep(0.5)

        self.assertGreaterEqual(mock_logger.error.call_count, 3)

        messages = [call.args[0] for call in mock_logger.error.call_args_list]
        self.assertIn("Could not subscribe to queue test_queue with callback function _test_callback after 3 attempts", messages)
        self.assertTrue(any("Error while subscribing to queue test_queue with callback function _test_callback" in msg for msg in messages))

        service.close()

    @patch('datastructure.async_message_service.aio_pika.connect_robust')
    def test_unsubscribe(self, mock_connect):
        """Test that messages can be unsubscribed successfully"""
        mock_connect.return_value = self.mock_connection

        service = AsyncMessageService()

        def _test_callback(message):
            pass

        service.subscribe(
            _test_callback,
            "test_exchange_name",
            ExchangeType.DIRECT,
            "test_queue",
            "test_routing_key",
        )

        time.sleep(0.5)

        service.unsubscribe("test_queue")

        time.sleep(0.5)

        self.mock_queue.cancel.assert_called_with("consume_tag")
        self.mock_channel.close.assert_called()

        service.close()

    @patch('datastructure.async_message_service.aio_pika.connect_robust')
    def test_close(self, mock_connect):
        """Test that the service can be closed properly"""
        mock_connect.return_value = self.mock_connection

        service = AsyncMessageService()

        def call_back(message):
            pass

        service.subscribe(
            call_back,
            "test_exchange_name",
            ExchangeType.DIRECT,
            "test_queue",
            "test_routing_key",
        )
        time.sleep(0.5)
        service.publish(
            "test_message",
            "test_exchange_name",
            ExchangeType.DIRECT,
            "test_routing_key"
        )

        time.sleep(0.5)

        service.close()

        self.assertTrue(service.is_closed)
        self.mock_channel.close.assert_called()






