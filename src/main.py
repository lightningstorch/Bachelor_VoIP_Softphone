import argparse
import asyncio
import os
import threading
import time

import uvicorn
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


def parse_args():
    parser = argparse.ArgumentParser(
        description="VoIP Call Capture and Processing System for live or file-based capture.",
    )
    parser.add_argument(
        "--mode",
        choices=["live", "file"],
        default="file",
        help="Run default in live mode, or use file mode with a specified file path.",
    )
    parser.add_argument(
        "--file",
        type=str,
        default=captured_file_path,
        help="Path to the capture file when running in file mode.",
    )
    return parser.parse_args()

def start_api():
    """
    Starts the FastAPI application in a separate thread.
    """
    uvicorn.run("api.api:app", host="0.0.0.0", port=8000, log_level="warning")


def main():
    app_logger.info("System is starting...")

    # init the dicts and queues
    # the queue for capture_procider and packet_processor
    queue_threads = Queue()
    cleanup_queue = Queue()

    # initialise Components
    message_service = AsyncMessageService()
    Aggregator(message_service)
    manager_call_context = ManagerCallContext(message_service, cleanup_queue)

    # init the Database
    init_db()

    # thread for API
    threading.Thread(target=start_api, daemon=True).start()
    time.sleep(2)  # wait for the API to start


    args = parse_args()

    if args.mode == "live":
        print("Running in live mode")
        capture_provider = CaptureProvider(message_service, "live", interface, queue_threads)
    elif args.mode == "file":
        print(f"Running in file mode with file: {args.file}")
        capture_provider = CaptureProvider(message_service, "file", os.path.abspath(captured_file_path), queue_threads)

    packet_processor_thread = PacketProcessor(message_service, queue_threads, manager_call_context, cleanup_queue)

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
