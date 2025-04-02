import asyncio
import threading
import os
import time

import pyshark

from Datastructure.dataclass import Call, EventType
from Datastructure.event_bus import EventBus
from src.my_logging.log_config import eventbus_logger, app_logger
from config.config import server_ip, interface
from .packet_processor import sip_process, rtp_process

class SipRecognizer(threading.Thread):
    def __init__(self, eventbus):
        super().__init__()
        self.daemon = True
        self._eventbus = eventbus
        self.context_ready = threading.Event()


    def run(self):
        app_logger.debug("Starting SIP recognize thread")
        print("Starting file processor thread")

        # capture need an asyncio for execution
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        while True:
            # read network dumps for SIP and RTP packets
            capture = pyshark.LiveCapture(interface=f'{interface}', display_filter=f'(sip or rtp) and ip.dst == {server_ip}')

            try:
                for packet in capture.sniff_continuously():
                    if 'SIP' in packet:
                        print("SIP packet detected in live capture")
                        app_logger.debug("SIP packet detected in live capture")

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
                app_logger.error(f"Problem occurred while live capture for 'sip': {e}")
            finally:
                capture.close()

            time.sleep(0.5)

        # file end -> Terminate the thread
        #app_logger.info("Terminate SIP precognizer thread")


    def set_context_ready(self):
        self.context_ready.set()