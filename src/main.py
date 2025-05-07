import time
import os

from config.config import captured_file_path, interface
from data_collection.packet_monitor import PacketMonitor
from datastructure.aggregator import Aggregator
from datastructure.dataclass import Call, EventType
from datastructure.event_bus import EventBus
from my_logging.log_config import app_logger

from datastructure.database.database import init_db



def main():
    app_logger.info("System is starting...")

    # initialise Components
    eventbus = EventBus()
    aggregator = Aggregator(eventbus)

    # for development
    #init_db()

    # to init the call Context
    eventbus.subscribe(EventType.CALL_INIT, main_call_init)

    # file to the network dumps
    file_path = os.path.abspath(captured_file_path)
    life_capture = False

    if life_capture:
        packet_monitor = PacketMonitor(eventbus, "live", interface)
    else:
        packet_monitor = PacketMonitor(eventbus, "file", os.path.abspath(captured_file_path))

    packet_monitor.start()

    # Test the wait for rtp packets
    time.sleep(0.5)
    packet_monitor.set_context_ready()

    packet_monitor.join()



def main_call_init(event):
    print("Now handle the init --> TODO Implementation")


if __name__ == '__main__':
    main()
