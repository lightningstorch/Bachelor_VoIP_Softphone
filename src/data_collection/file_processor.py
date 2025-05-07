import asyncio
import threading
import os
import pyshark

from datastructure.dataclass import Call, EventType
from datastructure.event_bus import EventBus
from src.my_logging.log_config import eventbus_logger, app_logger
from config.config import server_ip
from .packet_processor import sip_process, rtp_process

class FileProcessor(threading.Thread):
    def __init__(self, file_path, eventbus):
        super().__init__()
        self._file_path = file_path
        self.daemon = True
        self._eventbus = eventbus
        self.context_ready = threading.Event()


    def run(self):
        app_logger.debug("Starting file processor thread")

        # validate file
        if not self.validate_file():
            app_logger.error(f"Terminate thread because of invalid file path or file extension {self._file_path}")
            return

        # capture need an asyncio for execution
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        # read network dumps for SIP and RTP packets
        capture = pyshark.FileCapture(input_file= self._file_path, display_filter=f'(sip or rtp) and ip.dst == {server_ip}')

        try:
            for packet in capture:
                if 'SIP' in packet:
                    print("SIP packet detected")
                    app_logger.debug("SIP packet detected")

                    # sip processing
                    sip_process(packet, self._eventbus)
                # elif 'RTP' in packet:
                #     print("RTP packet detected")
                #     #app_logger.debug("RTP packet detected")
                #
                #     # wait until context stuff is ready
                #     self.context_ready.wait()
                #
                #     # fill the buffer with RTP Packets
                #     rtp_process(packet, self._eventbus)

        except Exception as e:
            app_logger.error(f"Problem occurred while parsing the document for 'sip': {e}")
        finally:
            capture.close()

        # file end -> Terminate the thread
        app_logger.info("Terminate file processor thread")


    def set_context_ready(self):
        self.context_ready.set()


    def validate_file(self) -> bool:
        # check if the file is reachable
        if not os.path.isfile(self._file_path) and not os.access(self._file_path, os.R_OK):
            app_logger.error(f"File {self._file_path} does not exist or is not readable")
            return False

        # check the file of the correct file extension (network dumps)
        _, ext = os.path.splitext(self._file_path)
        ext = ext.lower()
        allowed_extensions = ['.pcap', '.pcapng']

        if ext not in allowed_extensions:
            app_logger.error(f"File extension must be one of {allowed_extensions} and not {ext}")
            return False

        app_logger.debug(f"File is valid: {self._file_path}")
        return True

