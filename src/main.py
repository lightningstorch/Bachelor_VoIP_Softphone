import os.path
import threading
import time
import uvicorn

from queue import Queue, Empty
from call_context.manager_call_context import ManagerCallContext
from config.config import captured_file_path, interface, admin_username, admin_password
from data_collection.capture_provider import CaptureProvider
from data_collection.packet_processor import PacketProcessor
from datastructure.aggregator import Aggregator
from datastructure.async_message_service import AsyncMessageService
from my_logging.log_config import app_logger, broadcast_log
from datastructure.database.database import init_db, get_user, set_user
from utils.auth import hash_password, initial_admin_password
from utils.program_state_manager import ProgramStateManager

#==================================
#         Global Variables
#==================================

# CaptureProvider and PacketProcessor instances
capture_provider: CaptureProvider | None = None
packet_processor: PacketProcessor | None = None
# Queues for inter-thread communication
queue_packets: Queue = Queue(maxsize=1000)
cleanup_queue: Queue = Queue()
# AsyncMessageService instance
message_service = AsyncMessageService()
# ManagerCallContext instance
manager_call_context = ManagerCallContext(message_service, cleanup_queue)

# Current mode and source for the capture provider
current_mode: str | None = None
current_source: str | None = None


#==================================
#           Functions
#==================================

def start_api():
    """
    Starts the FastAPI application in a separate thread.
    """
    uvicorn.run("api.api:app", host="0.0.0.0", port=8000, log_level="warning")

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

    if capture_provider:
        if capture_provider.is_alive():
            capture_provider.stop()
            capture_provider.join()
            _emptying_queue(queue_packets)

        broadcast_log("system", f"Change Mode to {mode} and Source to {source}")
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

def set_admin(username: str, password: str):
    """
    Sets the admin user in the database. If the user does not exist,
    it creates a new user with the provided username and hashed password.
    :param username: The username for the admin user.
    :param password: The password for the admin user.
    """
    db_user = get_user(username)
    if not db_user:
        password, generated = initial_admin_password(password)
        set_user(username, hash_password(password))
        if generated:
            app_logger.warning(
                f"Created admin user '{username}' with generated password '{password}'. "
                "Change it in the UI after the first login."
            )

def switch_mode(mode: str, source: str):
    """
    Switches the program mode and source for the CaptureProvider.
    If the current mode and source are the same as the provided ones, it does nothing.
    :param mode: The mode to switch to, either "live" or "file".
    :param source: The source to switch to, either an interface or a file path.
    """
    global current_mode, current_source

    state_manager = ProgramStateManager()
    switch = state_manager.switch_mode(mode, source)

    if not switch:
        return

    start_capture_provider(mode, source)


#==================================
#         Main Functions
#==================================

def main():
    """
    Main function to start the VoIP UI Dashboard application.
    Initializes the aggregator, database, API, and starts the capture provider.
    """
    app_logger.info("System is starting...")

    state_manager = ProgramStateManager()

    # Initialize the aggregator and Database
    Aggregator(message_service)
    init_db()

    # check if admin is already created
    set_admin(admin_username, admin_password)

    # init the API
    threading.Thread(target=start_api, daemon=True).start()
    time.sleep(2)  # wait for the API to start

    state_manager.set_mode("live")
    state_manager.set_source(interface)
    start_capture_provider(state_manager.get_mode(), state_manager.get_source())

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