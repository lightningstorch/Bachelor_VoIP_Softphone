import time
import os

from Datastructure.aggregator import Aggregator
from Datastructure.dataclass import Call, EventType
from Datastructure.event_bus import EventBus
from data_collection.file_processor import FileProcessor
from my_logging.log_config import app_logger



def main():
    app_logger.info("System is starting...")

    # initialise Components
    eventbus = EventBus()
    aggregator = Aggregator(eventbus)

    # to init the call Context
    eventbus.subscribe(EventType.CALL_INIT, main_call_init)

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





def main_call_init(event):
    print("Now handle the init --> TODO Implementation")


if __name__ == '__main__':
    main()
