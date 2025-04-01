import time
from datetime import datetime
import os

from Datastructure.dataclass import Call, EventType
from Datastructure.event_bus import EventBus
from data_collection.file_processor import FileProcessor
from src.my_logging.log_config import eventbus_logger, app_logger



def main():
    app_logger.info("System is starting...")

    eventbus = EventBus()

    # For test purposes
    eventbus.subscribe(EventType.NEW_CALL, handle_new_call)

    # file to the network dumps
    file_path = os.path.abspath(r"C:\Transfer\second_doc.pcapng")
    read_document = True

    if read_document:
        # thread erstellen
        file_processor = FileProcessor(file_path, eventbus)

        # thread laufen lassen
        file_processor.start()

        # Test the wait for rtp packets
        time.sleep(0.5)
        file_processor.set_context_ready()

        file_processor.join()

    # TODO Thread for SIP-recognize here as else





def handle_new_call(call: Call):
    print("Now handle the new call --> TODO Implementation")


if __name__ == '__main__':
    main()
