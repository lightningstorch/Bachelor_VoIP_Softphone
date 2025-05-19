import threading

from datastructure.async_message_service import AsyncMessageService


class CallContext:

    def __init__(self, call_id: str, message_service: AsyncMessageService):

        self._stop_event = threading.Event()
        self.call_id = call_id
        self.message_service = message_service


    def insert_ssrc(self):
        pass

    def enqueue_packet(self, ssrc: str, packet):
        pass



    def stop(self):
        """
        Stop the call context
        """
        self._stop_event.set()
