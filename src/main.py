import asyncio
import os
from queue import Queue
from typing import Tuple

from aio_pika import ExchangeType, IncomingMessage
from config.config import captured_file_path, interface
from data_collection.capture_provider import CaptureProvider
from data_collection.packet_processor import PacketProcessor
from datastructure.aggregator import Aggregator
from datastructure.async_message_service import AsyncMessageService, get_message_service
from my_logging.log_config import app_logger
from datastructure.database.database import init_db



def main():
    app_logger.info("System is starting...")

    # initialise Components
    message_service = AsyncMessageService()
    aggregator = Aggregator(message_service)

    # init the Database
    init_db()

    # init the dicts and queues
    # the queue for capture_procider and packet_processor
    queue_threads = Queue()

    # TODO threadsafe implementation
    # to recognize the SSRC from the rtp package for the respective call_id
    call_map: dict[Tuple[str, int, str, int], Tuple[str, str]] = {}

    # TODO threadsafe implementation
    # ssrc to call_id mapping
    ssrc_to_call_id: dict[str, Tuple[str, str]] = {}


    message_service.subscribe(
        callback_init_call,
        "INIT_CALL",
        ExchangeType.DIRECT,
        "main_init_call_queue"
    )



    life_capture = False

    if life_capture:
        capture_provider = CaptureProvider(message_service, "live", interface, queue_threads)
    else:
        capture_provider = CaptureProvider(message_service, "file", os.path.abspath(captured_file_path), queue_threads)

    packet_processor_thread = PacketProcessor(message_service, queue_threads, call_map, ssrc_to_call_id)

    capture_provider.start()
    packet_processor_thread.start()

    try:
        capture_provider.join()
    except KeyboardInterrupt:
        print("KeyboardInterrupt")

    finally:
        # shutdown the threads
        capture_provider.stop()
        capture_provider.join()
        packet_processor_thread.stop()
        packet_processor_thread.join()

        # shutdown the message_service
        message_service.close()

def callback_init_call(message: IncomingMessage):
    print("Callback function for INIT_CALL in the main")
    print(message.body.decode('utf-8'))
    asyncio.run_coroutine_threadsafe(
        message.ack(),
        get_message_service().loop
    )
    #capture_provider.set_context_ready()


if __name__ == '__main__':
    main()
