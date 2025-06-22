import asyncio
import os
from queue import Queue

from aio_pika import IncomingMessage

from call_context.manager_call_context import ManagerCallContext
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
    manager_call_context = ManagerCallContext(message_service)


    # init the Database
    init_db()

    # init the dicts and queues
    # the queue for capture_procider and packet_processor
    queue_threads = Queue()

    life_capture = False

    if life_capture:
        capture_provider = CaptureProvider(message_service, "live", interface, queue_threads)
    else:
        capture_provider = CaptureProvider(message_service, "file", os.path.abspath(captured_file_path), queue_threads)

    packet_processor_thread = PacketProcessor(message_service, queue_threads, manager_call_context)

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

        # shutdown the CallContextManager
        manager_call_context.shutdown_all_calls()

        # shutdown the message_service
        message_service.close()


if __name__ == '__main__':
    main()
