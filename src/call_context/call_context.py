import threading
from queue import Queue, Empty

from analysis.audio_analysis import AudioAnalysis
from analysis.buffer import Buffer
from datastructure.async_message_service import AsyncMessageService
from my_logging.log_config import app_logger


class CallContext:

    def __init__(self, call_id: str, message_service: AsyncMessageService):
        self.call_id = call_id
        self.message_service = message_service

        self._queues: dict[str, Queue] = {}
        self._analysers: dict[str, AudioAnalysis] = {}
        self._buffers : dict[str, Buffer] = {}
        self._buffer_size = 3

        self._stop_event = threading.Event()
        self.thread = threading.Thread(target=self.run, name=f"CallContextThread-{self.call_id}", daemon=True)
        self.thread.start()



    def insert_ssrc(self, ssrc: str):
        """
        Insert a new SSRC into the call context
        :param ssrc: The SSRC to insert
        """
        if ssrc not in self._queues:
            self._queues[ssrc] = Queue()
            self._buffers[ssrc] = Buffer(ssrc, self._buffer_size)
            self._analysers[ssrc] = AudioAnalysis(ssrc)

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
                    packet = queue.get(timeout=0.1)
                except Empty:
                    continue

                # insert in the buffer
                self._buffers[ssrc].add(packet)

                # check if the size is reached
                if self._buffers[ssrc].buffer_size_reached():
                    # get the data from the buffer
                    packet = self._buffers[ssrc].get()

                    print(f"BUFFER ------------- reached {self._buffers[ssrc].size()}")

                    # process the data
                    #self._analysers[ssrc].analyze_audio(packet)

                    # publish the results




    def _flush_buffers(self):
        """
        Flush the buffers for all SSRCs in the call context to process all remaining packages
        """
        for ssrc, queue in list(self._queues.items()):
            buffer_items = self._buffers[ssrc].flush()
            if buffer_items:
                # process the data
                self._analysers[ssrc].analyze_audio(buffer_items)

                # publish the results
                #self.message_service.publish(self.call_id, ssrc, buffer_items)




    def stop(self):
        """
        Stop the call context
        """
        self._stop_event.set()
        self.thread.join()
        self._flush_buffers()
