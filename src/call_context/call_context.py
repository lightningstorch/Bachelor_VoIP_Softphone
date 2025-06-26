import threading
from queue import Queue, Empty

from aio_pika import ExchangeType

from analysis.audio_analysis import AudioAnalysis
from analysis.buffer import Buffer
from config.config import default_audio_sample_rate
from datastructure.async_message_service import AsyncMessageService
from datastructure.dataclass_models import TalkingInterval, EventType
from my_logging.log_config import app_logger, call_context_logger


class CallContext:

    def __init__(self, call_id: str, message_service: AsyncMessageService):
        self.call_id = call_id
        self.message_service = message_service
        self.sample_rate = default_audio_sample_rate # Default sample rate for audio analysis

        self._queues : dict[str, Queue] = {}
        self._analysers : dict[str, AudioAnalysis] = {}
        self._buffers : dict[str, Buffer] = {}
        self._buffer_size = 5 # Number of packets to buffer before processing
        self._store_intervals : dict[str, list] = {} # ssrc -> list of intervals

        self._stop_event = threading.Event()
        self.thread = threading.Thread(target=self.run, name=f"CallContextThread-{self.call_id}", daemon=True)
        self.thread.start()

        self.intervals: dict[str, list] = {}

    def insert_ssrc(self, ssrc: str):
        """
        Insert a new SSRC into the call context
        :param ssrc: The SSRC to insert
        """
        if ssrc not in self._queues:
            self._queues[ssrc] = Queue()
            self._buffers[ssrc] = Buffer(ssrc, self._buffer_size)
            self._analysers[ssrc] = AudioAnalysis(ssrc, self.sample_rate)
            self.intervals[ssrc] = []

    def set_sample_rate(self, sample_rate: int):
        self.sample_rate = sample_rate

    def enqueue_packet(self, ssrc: str, packet):
        """
        Enqueue a packet to the call context
        :param ssrc: The SSRC of the packet
        :param packet: The packet to enqueue
        """
        if ssrc in self._queues:
            self._queues[ssrc].put(packet)
            #print(f"packet is inserted {packet.rtp.payload.binary_value}")
        else:
            app_logger.warning(f"SSRC '{ssrc}' not found in call context '{self.call_id}'.")

    def run(self):
        while not self._stop_event.is_set():
            for ssrc, queue in list(self._queues.items()):
                try:
                    packets = queue.get(timeout=0.1)
                except Empty:
                    continue

                # insert in the buffer
                self._buffers[ssrc].add(packets)

                # check if the size is reached
                if self._buffers[ssrc].buffer_size_reached():
                    # get the data from the buffer
                    packets = self._buffers[ssrc].get()

                    # process the data
                    speech_intervals = self._analysers[ssrc].analyze_audio(packets)

                    if speech_intervals:
                        print(f"Speech intervals for SSRC '{ssrc}': {speech_intervals}")
                        call_context_logger.debug(f"Speech intervals for SSRC '{ssrc}': {speech_intervals}")
                        self.intervals[ssrc].extend(speech_intervals)

                    self._send_intervals(speech_intervals, ssrc)

    def calculate_overlapping_intervals(self):
        """
        Calculate overlapping intervals between the SSRCs in the call context.
        This method compares the speech intervals of the first two SSRCs and finds overlaps.
        If there are more than two SSRCs, it only considers the first two for overlap calculation.
        It sends the overlapping intervals to the message service.
        """

        lists = list(self.intervals.items())
        (ssrc1, intervals1), (ssrc2, intervals2) = lists[0], lists[1]

        overlaps = []
        for start1, end1 in intervals1:
            for start2, end2 in intervals2:
                overlap_start = max(start1, start2)
                overlap_end = min(end1, end2)

                if overlap_start < overlap_end:
                    overlaps.append((overlap_start, overlap_end))

        self._send_intervals(speech_intervals=overlaps, type_interval="overlap")

    def _flush_buffers(self):
        """
        Flush the buffers for all SSRCs and process the remaining audio data.
        This method is called when the call context is stopped to ensure that any remaining audio data is processed.
        It analyzes the buffered audio data and sends the resulting speech intervals.
        """
        for ssrc, analyser in self._analysers.items():
            buffer_items = self._buffers[ssrc].flush()
            if buffer_items:
                speech_intervals = analyser.analyze_audio(buffer_items)
                if speech_intervals:
                    self._handle_intervals(ssrc, speech_intervals)

            last_interval = analyser.close()
            if last_interval:
                self._handle_intervals(ssrc, last_interval, label="Final speech interval")

    def stop(self):
        """
        Stop the call context
        """
        self._stop_event.set()
        self._flush_buffers()
        self.calculate_overlapping_intervals()
        self.thread.join()

#================================================
#           Helper methods
#================================================

    def _handle_intervals(self, ssrc: str, speech_intervals: list, label= "Speech intervals"):
        self._send_intervals(speech_intervals, ssrc)
        print(f"[FLUSH] {label} for SSRC '{ssrc}': {speech_intervals}")
        call_context_logger.debug(f"[FLUSH] {label} for SSRC '{ssrc}': {speech_intervals}")
        self.intervals[ssrc].extend(speech_intervals)

    def _send_intervals(self, speech_intervals: list, ssrc = None, type_interval= "speech"):
        """
        Send the speech intervals to the message service.
        :param ssrc: The SSRC of the audio stream.
        :param speech_intervals: The list of speech intervals to send.
        :param type_interval: The type of interval, e.g., "speech" or "overlap".
        """

        for (start, end) in speech_intervals:
            if ssrc not in self._store_intervals:
                self._store_intervals[ssrc] = []
            self._store_intervals[ssrc].append((start, end))

            # publish the results
            payload = TalkingInterval(
                type= type_interval,
                call_id=self.call_id,
                ssrc=ssrc,
                start=start,
                end=end
            ).model_dump_json()

            self.message_service.publish(
                payload,
                exchange_name="TALKING_SECTION",
                exchange_type=ExchangeType.DIRECT,
                routing_key="talking_section"
            )
