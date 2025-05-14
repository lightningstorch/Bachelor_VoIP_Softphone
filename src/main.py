import asyncio
import time
import os

import aio_pika
from aio_pika import ExchangeType, IncomingMessage

from config.config import captured_file_path, interface
from data_collection.capture_provider import CaptureProvider
from datastructure.aggregator import Aggregator
from datastructure.dataclass_models import Call, EventType
from datastructure.async_message_service import AsyncMessageService, get_message_service
from my_logging.log_config import app_logger

from datastructure.database.database import init_db



def main():
    app_logger.info("System is starting...")

    # initialise Components
    message_service = AsyncMessageService()
    aggregator = Aggregator(message_service)

    # for development
    #init_db()

    # to init the call Context
    message_service.subscribe(
        callback_init_call,
        "INIT_CALL",
        ExchangeType.DIRECT,
        "main_init_call_queue"
    )

    life_capture = False

    if life_capture:
        capture_provider = CaptureProvider(message_service, "live", interface)
    else:
        capture_provider = CaptureProvider(message_service, "file", os.path.abspath(captured_file_path))

    capture_provider.start()

    # Test the wait for rtp packets
    time.sleep(0.5)
    capture_provider.set_context_ready()

    try:
        capture_provider.join()
    except KeyboardInterrupt:
        print("KeyboardInterrupt")

    finally:
        # shutdown the capture_provider thread
        capture_provider.stop()
        capture_provider.join()

        # shutdown the message_service
        message_service.close()

# für the new RabbitMQ Message Service
def callback(message: IncomingMessage):
    print("Received a message")
    print(message.body.decode('utf-8'))
    asyncio.run_coroutine_threadsafe(
        message.ack(),
        get_message_service().loop
    )

def callback_init_call(message: IncomingMessage):
    print("Callback function for INIT_CALL in the main")
    print(message.body.decode('utf-8'))
    asyncio.run_coroutine_threadsafe(
        message.ack(),
        get_message_service().loop
    )

if __name__ == '__main__':
    main()
