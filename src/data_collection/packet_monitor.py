import threading
import asyncio
import time

import pyshark

from config.config import server_ip
from data_collection.packet_processor import process_packets
from my_logging.log_config import app_logger
from utils.validation import validate_file


class PacketMonitor(threading.Thread):
    def __init__(self, eventbus, source_type, source_value):
        super().__init__()
        self.daemon = True
        self.context_ready = threading.Event()

        self.source_type = source_type
        self.source_value = source_value

        self._eventbus = eventbus


    def run(self):
        app_logger.debug("Starting packet monitor thread")
        print("Starting packet monitor thread")

        display_filter = f'(sip or rtp) and ip.dst == {server_ip}'

        # this is needed for a file processing and sometimes also for live capture on windows
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        if self.source_type == 'live':
            app_logger.debug(f"Live capture on {self.source_value}")

            capture = None

            while True:
                try:
                    capture = pyshark.LiveCapture(interface=self.source_value, display_filter=display_filter)
                    for packet in capture.sniff_continuously():
                        process_packets(packet, self._eventbus, self.context_ready)

                except Exception as e:
                    app_logger.error(f"Problem occurred while live capture: {e}")
                finally:
                    try:
                        capture.close()
                    except Exception as e:
                        app_logger.error(f"Error while closing capture: {e}")

                time.sleep(0.5)

        elif self.source_type == 'file':
            if not validate_file(self.source_value):
                app_logger.error(f"Terminate thread because of invalid file path or file extension {self.source_value}")
                return

            app_logger.debug(f"File capture on {self.source_value}")

            try:
                capture = pyshark.FileCapture(input_file=self.source_value, display_filter=display_filter)
                for packet in capture:
                    process_packets(packet, self._eventbus, self.context_ready)

            except Exception as e:
                app_logger.error(f"Problem occurred while parsing the document: {e}")
            finally:
                    try:
                        loop.close()
                    except Exception as e:
                        app_logger.error(f"Error while closing loop: {e}")


    def set_context_ready(self):
        self.context_ready.set()


