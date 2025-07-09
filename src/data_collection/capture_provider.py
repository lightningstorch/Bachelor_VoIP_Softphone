import os
import threading
import asyncio
import pyshark

from threading import Event, Thread
from my_logging.log_config import app_logger
from utils.validation import validate_file


class CaptureProvider(Thread):
    def __init__(self, source_type, source_value, queue):
        super().__init__(daemon=True)
        self.daemon = True
        self._stop_event = Event()
        self.capture = None
        self.loop = None

        self.source_type = source_type
        self.source_value = source_value
        self.queue = queue

    def run(self):
        app_logger.debug(f"Starting capture provider thread in mode: {self.source_type}")
        print(f"Starting capture provider thread in mode: {self.source_type}")

        #display_filter = f'(sip or rtp) and ip.dst == {server_ip}'
        display_filter = f'(sip or rtp)'

        # this is needed for a file processing and sometimes also for live capture on windows
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        if self.source_type == 'live':
            self.live_capture(display_filter)
        elif self.source_type == 'file':
            self.file_capture(display_filter)

    def live_capture(self, display_filter):
        """
        Starts a live capture on the specified source interface.
        :param display_filter: The display filter to apply to the captured packets.
        """
        app_logger.debug(f"Live capture on {self.source_value}")

        while not self._stop_event.is_set():
            try:
                self.capture = pyshark.LiveCapture(interface=self.source_value, display_filter=display_filter)
                for packet in self.capture.sniff(packet_count=10, timeout=1):
                    if self._stop_event.is_set():
                        break

                    self.queue.put(packet)

            except Exception as e:
                app_logger.error(f"Problem occurred while live capture: {e}")
            finally:
                self.capture.close()
                self.capture = None
                self.loop.stop()
                self.loop.close()

    def file_capture(self, display_filter):
        """
        Starts a file capture on the specified file path.
        :param display_filter: The display filter to apply to the captured packets.
        """
        if not validate_file(self.source_value):
            app_logger.error(f"Terminate thread because of invalid file path or file extension {self.source_value}")
            return

        app_logger.debug(f"File capture on {self.source_value}")

        try:
            self.capture = pyshark.FileCapture(input_file=self.source_value, display_filter=display_filter)
            for packet in self.capture:
                if self._stop_event.is_set():
                    break

                self.queue.put(packet)

        except Exception as e:
            app_logger.error(f"Problem occurred while parsing the document: {e}")
        finally:
            self.capture.close()
            self.capture = None
            self.loop.stop()
            self.loop.close()

            if os.path.exists(self.source_value) and os.path.isfile(self.source_value):
                app_logger.debug(f"Removing file {self.source_value} after processing")
                # Remove the file after processing
                try:
                    os.remove(self.source_value)
                except Exception as e:
                    app_logger.error(f"Error removing file {self.source_value}: {e}")

    def stop(self):
        self._stop_event.set()
