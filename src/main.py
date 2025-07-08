import threading
import time
import uvicorn

from queue import Queue, Empty

from api.api import start_api
from call_context.manager_call_context import ManagerCallContext
from config.config import captured_file_path, interface
from data_collection.capture_provider import CaptureProvider
from data_collection.packet_processor import PacketProcessor
from datastructure.aggregator import Aggregator
from datastructure.async_message_service import AsyncMessageService
from my_logging.log_config import app_logger
from datastructure.database.database import init_db, set_program_mode

#==================================
#         Global Variables
#==================================

# CaptureProvider and PacketProcessor instances
capture_provider: CaptureProvider | None = None
packet_processor: PacketProcessor | None = None
# Queues for inter-thread communication
queue_packets: Queue = Queue()
cleanup_queue: Queue = Queue()
# AsyncMessageService instance
message_service = AsyncMessageService()
# ManagerCallContext instance
manager_call_context = ManagerCallContext(message_service, cleanup_queue)


#==================================
#           Functions
#==================================

def start_packet_processor():
    """
    Starts the PacketProcessor if it is not already running.
    If it is already running, it does nothing.
    """
    global packet_processor
    if packet_processor is None or not packet_processor.is_alive():
        packet_processor = PacketProcessor(
            message_service,
            queue_packets,
            manager_call_context,
            cleanup_queue
        )
        packet_processor.start()

def start_capture_provider(mode: str, source: str):
    """
    Starts the CaptureProvider with the specified mode and source.
    If a CaptureProvider is already running, it stops it before starting a new one.
    :param mode: The mode of operation, either "live" or "file".
    :param source: The source of the packets, either an interface or a file path.
    """
    global capture_provider
    if capture_provider and capture_provider.is_alive():
        capture_provider.stop()
        capture_provider.join()
        _emptying_queue(queue_packets)
        print(f"Change Mode to {mode} and Source to {source}")

    capture_provider = CaptureProvider(
        mode,
        source,
        queue_packets
    )
    capture_provider.start()

    start_packet_processor()

def stop_program():
    """
    Stops the program gracefully by shutting down all threads and services.
    """
    app_logger.info("Stopping the program...")

    if capture_provider:
        capture_provider.stop()
        capture_provider.join()

    if packet_processor:
        packet_processor.stop()
        packet_processor.join()

    # shutdown the CallContextManager
    manager_call_context.shutdown_all_calls()

    # shutdown the message_service
    message_service.close()

    app_logger.info("Program stopped successfully.")

#==================================
#         Main Functions
#==================================

def main():
    """
    Main function to start the VoIP UI Dashboard application.
    Initializes the aggregator, database, API, and starts the capture provider.
    """
    app_logger.info("System is starting...")

    # Initialize the aggregator and Database
    Aggregator(message_service)
    init_db()

    # init the API
    threading.Thread(target=start_api, daemon=True).start()
    time.sleep(2)  # wait for the API to start

    mode = "live"
    source = interface if mode == "live" else captured_file_path
    set_program_mode(mode)
    start_capture_provider(mode, source)

    threading.Event().wait()

    stop_program()

if __name__ == '__main__':
    main()

#==================================
#         Helper functions
#==================================

def _emptying_queue(queue: Queue):
    """
    Empties the given queue by removing all items without blocking.
    :param queue: The queue to be emptied.
    """
    while not queue.empty():
        try:
            queue.get_nowait()
        except Empty:
            break