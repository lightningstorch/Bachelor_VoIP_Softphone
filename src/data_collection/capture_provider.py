import threading
import asyncio
import time

import pyshark

from config.config import server_ip
from data_collection.packet_processor import process_packets
from my_logging.log_config import app_logger
from utils.validation import validate_file


class CaptureProvider(threading.Thread):
    def __init__(self, message_service, source_type, source_value):
        super().__init__()
        self.daemon = True
        self.context_ready = threading.Event()
        self._stop_event = threading.Event()
        self.capture = None
        self.loop = None

        self.source_type = source_type
        self.source_value = source_value

        self._message_service = message_service


    def run(self):
        app_logger.debug("Starting packet monitor thread")
        print("Starting packet monitor thread")

        display_filter = f'(sip or rtp) and ip.dst == {server_ip}'

        # this is needed for a file processing and sometimes also for live capture on windows
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        if self.source_type == 'live':
            self.live_capture(display_filter)
        elif self.source_type == 'file':
            self.file_capture(display_filter)


    def live_capture(self, display_filter):
        app_logger.debug(f"Live capture on {self.source_value}")

        while not self._stop_event.is_set():
            try:
                self.capture = pyshark.LiveCapture(interface=self.source_value, display_filter=display_filter)
                for packet in self.capture.sniff_continuously():
                    process_packets(packet, self._message_service, self.context_ready)

            except Exception as e:
                app_logger.error(f"Problem occurred while live capture: {e}")
            finally:
                self.capture.close()
                self.capture = None

    def file_capture(self, display_filter):
        if not validate_file(self.source_value):
            app_logger.error(f"Terminate thread because of invalid file path or file extension {self.source_value}")
            return

        app_logger.debug(f"File capture on {self.source_value}")

        try:
            self.capture = pyshark.FileCapture(input_file=self.source_value, display_filter=display_filter)
            for packet in self.capture:
                process_packets(packet, self._message_service, self.context_ready)

        except Exception as e:
            app_logger.error(f"Problem occurred while parsing the document: {e}")
        finally:
            self.capture.close()
            self.capture = None

    def set_context_ready(self):
        self.context_ready.set()

    def stop(self):
        self._stop_event.set()


