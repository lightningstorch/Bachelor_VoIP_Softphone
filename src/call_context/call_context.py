import threading
from queue import Queue, Empty

from aio_pika import ExchangeType

from analysis.audio_analysis import AudioAnalysis
from analysis.buffer import Buffer
from datastructure.async_message_service import AsyncMessageService
from datastructure.dataclass_models import TalkingInterval
from my_logging.log_config import app_logger


class CallContext:

    def __init__(self, call_id: str, message_service: AsyncMessageService):
        self.call_id = call_id
        self.message_service = message_service

        self._queues : dict[str, Queue] = {}
        self._analysers : dict[str, AudioAnalysis] = {}
        self._buffers : dict[str, Buffer] = {}
        self._buffer_size = 5 # Number of packets to buffer before processing
        self._store_intervals : dict[str, list] = {} # ssrc -> list of intervals

        self._stop_event = threading.Event()
        self.thread = threading.Thread(target=self.run, name=f"CallContextThread-{self.call_id}", daemon=True)
        self.thread.start()

        self.intervals = {}



    def insert_ssrc(self, ssrc: str):
        """
        Insert a new SSRC into the call context
        :param ssrc: The SSRC to insert
        """
        if ssrc not in self._queues:
            self._queues[ssrc] = Queue()
            self._buffers[ssrc] = Buffer(ssrc, self._buffer_size)
            self._analysers[ssrc] = AudioAnalysis(ssrc)
            self.intervals[ssrc] = []

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
            app_logger.warning(f"SSRC {ssrc} not found in call context {self.call_id}.")



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

                    #print(f"BUFFER ------------- reached {self._buffers[ssrc].size()}")

                    # process the data
                    # speech_intervals = self._analysers[ssrc].analyze_audio(packets)
                    #
                    # # 3) Gib nur dann etwas aus, wenn result nicht leer ist
                    # if speech_intervals:
                    #     print(f"Speech intervals for SSRC {ssrc}: {speech_intervals}")
                    #     self.intervals[ssrc].extend(speech_intervals)
                    # #print(f"Speech intervals for SSRC {ssrc}: {speech_intervals}")

                    # # store the intervals for overlapping speech detection
                    # for (start, end) in speech_intervals:
                    #     if ssrc not in self._store_intervals:
                    #         self._store_intervals[ssrc] = []
                    #     self._store_intervals[ssrc].append((start, end))
                    #     print(f"Speech interval for SSRC {ssrc}: {start} - {end}")
                    #
                    #     # publish the results
                    #     payload = TalkingInterval(
                    #         type= "speech",
                    #         call_id= self.call_id,
                    #         ssrc= ssrc,
                    #         start= start,
                    #         end= end
                    #     ).model_dump_json()
                    #
                    #     self.message_service.publish(
                    #         payload,
                    #         exchange_name="TalkingInterval",
                    #         exchange_type=ExchangeType.DIRECT,
                    #         routing_key="TalkingInterval"
                    #     )

    def _flush_buffers(self):
        for ssrc, queue in list(self._queues.items()):
            buffer_items = self._buffers[ssrc].flush()
            if buffer_items:
                speech_intervals = self._analysers[ssrc].analyze_audio(buffer_items)
                if speech_intervals:
                    print(f"[FLUSH] Speech intervals for SSRC {ssrc}: {speech_intervals}")
                    self.intervals[ssrc].extend(speech_intervals)

        for ssrc, analyser in self._analysers.items():
            last_interval = analyser.close()
            if last_interval is not None:
                print(f"[FLUSH] Final speech interval for SSRC {ssrc}: {last_interval}")
                self.intervals[ssrc].extend(last_interval)



    def calculate_overlapping_intervals(self):
        pass



    def stop(self):
        """
        Stop the call context
        """
        self._stop_event.set()
        self._flush_buffers()
        self.calculate_overlapping_intervals()
        self.thread.join()

