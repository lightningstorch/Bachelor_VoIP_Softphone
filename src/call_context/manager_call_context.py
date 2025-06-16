import threading
from collections import defaultdict
from typing import DefaultDict

from call_context.call_context import CallContext
from datastructure.async_message_service import AsyncMessageService
from my_logging.log_config import app_logger


class ManagerCallContext:
    """
    ManagerCallContext is responsible for managing the call contexts.
    It creates, retrieves, and deletes call contexts based on the call ID.
    It also handles the insertion of SSRC into the call context.
    It uses a thread-safe dictionary to store the call contexts and a lock to ensure thread safety.
    """

    def __init__(self, message_service: AsyncMessageService):
        # to store all the call contexts with SSRC under the call_id
        self.all_contexts: dict[str, CallContext] = {}
        # [call_id] -> [list of ssrc]
        self._known_ssrc: DefaultDict[str, set[str]] = defaultdict(set)
        self.lock = threading.Lock()
        self.message_service = message_service

    def get_call_context(self, call_id: str):
        """
        Get the call context by call_id

        :param call_id: The call ID to search for
        :return: Tuple with CallContext and a list of SSRC or None
        """
        if call_id in self.all_contexts:
            with self.lock:
                return self.all_contexts[call_id]
        else:
            app_logger.debug(f"Call ID '{call_id}' not found.")
            return None

    def create_or_insert_call_context(self, call_id: str, ssrc: str):
        """
        Create a new call context or insert an SSRC into an existing one.

        :param call_id: The call ID to create the context for
        :param ssrc: the RTP Stream SSRC to insert in call context
        """
        with self.lock:
            call_context = self.all_contexts.get(call_id)
            if call_context is None:
                call_context = CallContext(call_id, self.message_service)
                self.all_contexts[call_id] = call_context
                app_logger.debug(f"Call context created for Call ID '{call_id}' with SSRC '{ssrc}'.")

            if ssrc not in self._known_ssrc[call_id]:
                call_context.insert_ssrc(ssrc)
                self._known_ssrc[call_id].add(ssrc)
                app_logger.debug(f"SSRC '{ssrc}' added to existing Call ID context '{call_id}'.")

        return call_context

    def enqueue_packet(self, call_id: str, ssrc: str, packet):
        """
        Enqueue a packet to the call context

        :param ssrc: ssrc of the packet
        :param call_id: The call ID to enqueue the packet for
        :param packet: The packet to enqueue
        """
        call_context = self.create_or_insert_call_context(call_id, ssrc)
        call_context.enqueue_packet(ssrc, packet)

    def end_call(self, call_id: str):
        """
        End a call by call_id
        """
        if call_id in self.all_contexts:
            with self.lock:
                if call_id not in self.all_contexts:
                    app_logger.debug(f"Call ID '{call_id}' not found.")

                call_context = self.all_contexts.pop(call_id)
                call_context.stop()

    def shutdown_all_calls(self):
        """
        Shutdown all calls
        """
        with self.lock:
            for call_id, call_context in self.all_contexts.items():
                call_context.stop()
                del self.all_contexts[call_id]
                app_logger.debug(f"Call ID '{call_id}' stopped and removed.")
