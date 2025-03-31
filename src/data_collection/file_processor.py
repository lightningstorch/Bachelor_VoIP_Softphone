import asyncio
import threading
import os
import pyshark

from Datastructure.dataclass import Event, EventType
from Datastructure.event_bus import EventBus
from src.my_logging.log_config import eventbus_logger, app_logger
from config.config import server_ip

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
        # TODO save the IP-Address of the server in a separate config file.
        capture = pyshark.FileCapture(input_file= self._file_path, display_filter=f'(sip or rtp) and ip.dst == {server_ip}')

        try:
            for packet in capture:
                if 'SIP' in packet:
                    print("SIP packet detected")
                    app_logger.debug("SIP packet detected")
                    # sip processing
                    self.sip_process(packet)
                elif 'RTP' in packet:
                    print("RTP packet detected")
                    app_logger.debug("RTP packet detected")

                    # wait until context stuff is ready
                    self.context_ready.wait()

                    # fill the buffer with RTP Packets
                    self.rtp_process(packet)

        except Exception as e:
            app_logger.error(f"Problem occurred while parsing the document for 'sip': {e}")
        finally:
            capture.close()

        # file end -> Terminate the thread
        app_logger.info("Terminate file processor thread")


    # TODO implement sip processing
    def sip_process(self, sip_packet):
        sip = sip_packet.sip

        if hasattr(sip, 'request_line'):
            if sip.method == 'INVITE':
                # wants to be a call
                print(sip.method)
            elif sip.method == 'ACK':
                # Call is accepted
                print(sip.method)
            elif sip.method == 'BYE':
                # call wants to be ended
                print(sip.method)
            else:
                print("other request_line")

        elif hasattr(sip, 'status_line'):
            if int(sip.status_code) == 100:
                # trying
                print(f"{sip.status_code}: {sip.status_line}")
            elif int(sip.status_code) == 180:
                # ringing
                print(f"{sip.status_code}: {sip.status_line}")
            elif int(sip.status_code) == 200:
                method = getattr(sip, 'cseq_method', 'UNKNOWN')
                if method == 'INVITE':
                    # call will be inizialized
                    print(f"{sip.status_code}: {sip.status_line} invite")
                elif method == 'BYE':
                    # call is now ended
                    print(f"{sip.status_code}: {sip.status_line} BYE")

        return


    # TODO implement rtp processing
    def rtp_process(self, rtp_packet):
        return


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

