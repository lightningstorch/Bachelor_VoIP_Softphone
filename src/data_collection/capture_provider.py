import json
import os
import subprocess
import threading
import asyncio
import pyshark
import time

from threading import Event, Thread
from my_logging.log_config import app_logger
from test_buffer import buffer
from utils.packet_parsing import handle_duplicates
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
        self.count = 10 # Number of packets to process before sleeping (file capture)

    def run(self):
        app_logger.debug(f"Starting capture provider thread in mode: {self.source_type}")
        print(f"Starting capture provider thread in mode: {self.source_type}")

        display_filter = f'(sip or rtp)'

        if self.source_type == 'live':
            self.live_capture(display_filter)
        elif self.source_type == 'file':
            self.file_capture(display_filter)

    def live_capture(self, display_filter):
        """
        Processes a live capture using TShark.
        This method captures packets from a live network interface using TShark,
        applies a display filter, and processes the output in real-time.
        The Tshark command output is parsed with a special focus on handling dupplicates
        in the JSON output and pushing the parsed packets into a queue for further processing.
        :param display_filter: The display filter to apply to the captured packets.
        """
        app_logger.debug(f"Live capture on {self.source_value}")

        tshark_cmd = [
            'tshark',
            '-i', self.source_value,
            '-Y', display_filter,
            '-T', 'json',
            '-l'
        ]

        subproc = None

        try:
            subproc = subprocess.Popen(
                tshark_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1  # Line-buffered output
            )


            buffer = "" # Buffer to accumulate JSON objects
            brace_level = 0 # To track the level of nested braces

            # Read each line from the output of TShark and process it
            for line in subproc.stdout:

                if self._stop_event.is_set():
                    app_logger.debug("Stopping live capture due to stop event.")
                    break

                # check the nested braces level to determine if we have a complete JSON object
                for ch in line:
                    buffer += ch
                    if ch == "{":
                        brace_level += 1
                    elif ch == "}":
                        brace_level -= 1

                # If we have a complete JSON object (brace_level is 0), process the buffer
                if brace_level == 0 and buffer.strip():
                    text = buffer.strip().rstrip(",")
                    try:
                        # parse the accumulated JSON text
                        pkt = json.loads(text, object_pairs_hook=handle_duplicates)
                        self.queue.put(pkt)

                    except json.JSONDecodeError as e:
                        app_logger.error(f"Error occured by parsing Json: {e}")

                    buffer = ""

        except KeyboardInterrupt:
            app_logger.info("Error occurred during live capture, stopping...")

        finally:
            if subproc and subproc.poll() is None:
                app_logger.debug("Terminating TShark subprocess.")
                subproc.terminate()
                try:
                    subproc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    app_logger.error("TShark process did not terminate in time, force killing it.")
                    subproc.kill()
                    subproc.wait()

    def file_capture(self, display_filter):
        """
        Processes a file capture using TShark.
        :param display_filter: The display filter to apply to the captured packets.
        :raises: Exception if the file is invalid or if TShark fails to process it.
        :raises: JSONDecodeError if the output from TShark is not valid JSON.
        :raises: FileNotFoundError if the specified file does not exist.
        """
        if not validate_file(self.source_value):
            app_logger.error(f"Terminate thread because of invalid file path or file extension {self.source_value}")
            return

        app_logger.debug(f"File capture on {self.source_value} via tshark")

        tshark_cmd = [
            'tshark',
            '-r', self.source_value,
            '-Y', display_filter,
            '-T', 'json'
        ]

        try:
            output = subprocess.check_output(tshark_cmd, text=True)
            packets = json.loads(output, object_pairs_hook=handle_duplicates)

            count = self.count # sleeptime after every 5 packets

            for packet in packets:
                if self._stop_event.is_set():
                    break

                self.queue.put(packet)
                # a sleep mechanism to control the flow of packet processing
                # this is to avoid overwhelming the queue and allow other threads to process
                # packets in the queue (otherwise the program didn't work correctly)
                count -= 1
                if count <= 0:
                    time.sleep(0.001)  # Small delay to allow other threads to process
                    count = self.count

        except subprocess.CalledProcessError as e:
            app_logger.error(f"Error by TShark: {e}")

        except json.JSONDecodeError as e:
            app_logger.error(f"Invalid JSON output: {e}")

        finally:
            if os.path.exists(self.source_value) and os.path.isfile(self.source_value):
                app_logger.debug(f"Removing file {self.source_value} after processing")
                # Remove the file after processing
                try:
                    os.remove(self.source_value)
                except Exception as e:
                    app_logger.error(f"Error removing file {self.source_value}: {e}")

    def stop(self):
        app_logger.debug(f"Stop called on capture_provider {self.name}")
        self._stop_event.set()
