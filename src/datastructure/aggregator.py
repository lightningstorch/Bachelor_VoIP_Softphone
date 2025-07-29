import asyncio
import json

from datetime import datetime
from aio_pika import IncomingMessage, ExchangeType
from datastructure.database.database import store_call_start, store_call_end, store_ssrc, store_talking_sections
from datastructure.dataclass_models import CallInfo, ParticipantInfo, TalkingInterval
from typing import Dict
from my_logging.log_config import app_logger, aggregator_logger, broadcast_log


class Aggregator:
    def __init__(self, message_service):
        self.message_service = message_service
        self._call_buffer: Dict[str, CallInfo] = {}

        self.message_service.subscribe(self.aggregator_new_call, "NEW_CALL", ExchangeType.DIRECT, "aggregator_new_call_queue", "new_call").result(timeout=5)
        self.message_service.subscribe(self.aggregator_participation, "PARTICIPANTS", ExchangeType.DIRECT, "aggregator_participation_queue", "participation").result(timeout=5)
        self.message_service.subscribe(self.aggregator_server_info, "SERVER_INFO", ExchangeType.DIRECT, "aggregator_server_data_queue", "server_info").result(timeout=5)
        self.message_service.subscribe(self.aggregator_ack, "ACK", ExchangeType.DIRECT, "aggregator_ack_queue", "ack").result(timeout=5)
        self.message_service.subscribe(self.aggregator_call_end, "CALL_END", ExchangeType.DIRECT, "aggregator_call_end_queue", "end_call").result(timeout=5)
        self.message_service.subscribe(self.aggregator_call_decline, "CALL_DECLINE", ExchangeType.DIRECT, "aggregator_call_decline_queue", "call_decline").result(timeout=5)
        self.message_service.subscribe(self.aggregator_ssrc, "SSRC", ExchangeType.DIRECT, "aggregator_ssrc_queue", "ssrc").result(timeout=5)
        self.message_service.subscribe(self.aggregator_talking_section, "TALKING_SECTION", ExchangeType.DIRECT, "aggregator_talking_section_queue", "talking_section").result(timeout=5)

        app_logger.debug("Aggregator: Starting Aggregator")

    def aggregator_new_call(self, message: IncomingMessage):
        """
        Handles the new call message from the message service.
        This method is called when a new call message is received.
        It decodes the message body, extracts the call ID and caller information,
        and stores it in the call buffer.
        :param message: The incoming message contains the call information.
        """
        # confirm receipt of the message
        asyncio.create_task(message.ack())
        body = json.loads(message.body.decode())

        # store in the buffer
        self._call_buffer[body.get("call_id")] = CallInfo(caller=body.get("caller"))

        broadcast_log("New Call:", f"A new call is detected with the call id '{body.get('call_id')}'")

        print(f"Aggregator: New call is temporarily saved: '{body.get('call_id')}'")
        aggregator_logger.debug(f"Aggregator: New call is temporarily saved: '{body.get('call_id')}'")

    def aggregator_participation(self, message: IncomingMessage):
        """
        Handles the participation message from the message service.
        This method is called when a participation message is received.
        It decodes the message body, extracts the call ID, user information,
        and other fields, and updates the participant's information in the call buffer.
        :param message: The incoming message contains the participation information.
        """
        # confirm receipt of the message
        asyncio.create_task(message.ack())
        body = json.loads(message.body.decode())

        if body.get('call_id') not in self._call_buffer:
            aggregator_logger.warning(f"Aggregator: Call ID {body.get('call_id')} not found in buffer")
            return

        fields = {}
        if "ip_address" in body:
            fields["ip_address"] = body["ip_address"]
        if "media_port" in body and body["media_port"] is not None:
            fields["media_port"] = int(body["media_port"])
        if "mime_type" in body:
            fields["mime_type"] = body["mime_type"]

        participant = self.get_participant(body)

        for key, value in fields.items():
            setattr(participant, key, value)

        aggregator_logger.debug(f"Aggregator: Participant {body.get('user')} updated with all fields for call_id {body.get('call_id')}")

        self._store(body.get("call_id"))

    def aggregator_server_info(self, message: IncomingMessage):
        """
        Handles the server information message from the message service.
        This method is called when a server information message is received.
        It decodes the message body, extracts the call ID, server IP, and server port,
        and updates the participant's server information in the call buffer.
        :param message: The incoming message contains the server information.
        """
        asyncio.create_task(message.ack())
        body = json.loads(message.body.decode())

        if body.get('call_id') not in self._call_buffer:
            aggregator_logger.warning(f"Aggregator: Call ID {body.get('call_id')} not found in buffer")
            return

        participant = self.get_participant(body)

        participant.server_ip = body["server_ip"]
        participant.server_port = int(body["server_port"]) if body["server_port"] is not None else None

        self._store(body.get("call_id"))

    def aggregator_ack(self, message: IncomingMessage):
        """
        Handles the acknowledgment message from the message service.
        This method is called when an acknowledgment message is received.
        It decodes the message body, extracts the call ID and start time,
        and updates the call buffer with the start time.
        :param message: The incoming message contains the acknowledgment information.
        """
        # confirm receipt of the message
        asyncio.create_task(message.ack())
        body = json.loads(message.body.decode())

        # Call was not answered -> Call decline
        if body.get("call_id") not in self._call_buffer:
            return

        self._call_buffer[body.get("call_id")].start_time = datetime.fromisoformat(body.get("start_time"))

        self._call_buffer[body.get("call_id")].ack_received = True

        broadcast_log("Ack:", f"The Call is accepted with this Data '{self._call_buffer[body.get("call_id")]}'")
        print(f"Aggregator Buffer: {self._call_buffer[body.get("call_id")]}")

        self._store(body.get("call_id"))

    def aggregator_call_end(self, message: IncomingMessage):
        """
        Handles the call end message from the message service.
        This method is called when a call end message is received.
        It decodes the message body, extracts the call ID and end time,
        updates the call buffer with the end time, and removes the call from the buffer.
        :param message: The incoming message contains the call end information.
        """
        # confirm receipt of the message
        asyncio.create_task(message.ack())
        body = json.loads(message.body.decode())

        # save directly in the database
        self._call_buffer[body.get("call_id")].end_time = datetime.fromisoformat(body.get("end_time"))
        print(self._call_buffer[body.get("call_id")])

        # delete the element in the buffer and save it to the database
        call_info = self._call_buffer.pop(body.get("call_id"))
        store_call_end(body.get("call_id"), call_info)

        aggregator_logger.info(f"Call ID '{body.get("call_id")}' has been finished and stored in db")

        broadcast_log(f"Call End {body.get("call_id")}:", f"The Call is finished")

        print(f"Aggregator: Call ID '{body.get("call_id")}' has been finished and stored in db")

    def aggregator_call_decline(self, message: IncomingMessage):
        """
        Handles the call decline message from the message service.
        This method is called when a call decline message is received.
        It decodes the message body, extracts the call ID, and removes the call from the buffer.
        :param message: The incoming message contains the call decline information.
        """
        # confirm receipt of the message
        asyncio.create_task(message.ack())
        body = json.loads(message.body.decode())

        # removed because the call is decline
        remove_call_id = self._call_buffer.pop(body.get("call_id"))
        if remove_call_id is not None:
            print(f"Removing call id '{body.get("call_id")}'")

            broadcast_log("Call Decline:", f"Call ID '{body.get('call_id')}' has been declined")

            aggregator_logger.info(f"Call ID '{body.get("call_id")}' has been declined")

    def aggregator_ssrc(self, message: IncomingMessage):
        """
        Handles the SSRC message from the message service.
        This method is called when an SSRC message is received.
        It decodes the message body, extracts the call ID, SSRC, and user information,
        and updates the participant's SSRC in the call buffer.
        :param message: The incoming message contains the SSRC information.
        """
        # confirm receipt of the message
        asyncio.create_task(message.ack())
        body = json.loads(message.body.decode())

        participant = next((p for p in self._call_buffer[body.get("call_id")].participants if p.user == body.get("user")), None)

        if participant:
            participant.ssrc = body.get("ssrc")

        if self._call_buffer[body.get("call_id")].stored:
            store_ssrc(body.get("call_id"), body.get("ssrc"), body.get("user"))
            aggregator_logger.debug(f"SSRC '{body.get('ssrc')}' has been stored in db")
            broadcast_log("aggregator:", f"SSRC '{body.get('ssrc')}' has been stored in db")
        else:
            aggregator_logger.debug(f"SSRC '{body.get('ssrc')}' detection to fast, save it in the buffer")
            broadcast_log("SSRC Detection:", f"SSRC '{body.get('ssrc')}' detection to fast, save it in the buffer - ack will process it later")
            print(f"SSRC '{body.get('ssrc')}' detection to fast, save it in the buffer - ack will process it later")

    def aggregator_talking_section(self, message: IncomingMessage):
        """
        Handles the talking section message from the message service.
        This method is called when a talking section message is received.
        It decodes the message body, extracts the type, call ID, SSRC, start time, and end time,
        and stores the talking section in the database.
        :param message: The incoming message contains the talking section information.
        """
        # confirm receipt of the message
        asyncio.create_task(message.ack())
        body = json.loads(message.body.decode())

        # if the call_id is not stored in the db yet, store it
        if body.get("call_id") in self._call_buffer and not self._call_buffer[body.get("call_id")].stored:
            self._store(body.get("call_id"))

        store_talking_sections(
            TalkingInterval(
                type=body.get("type"),
                call_id=body.get("call_id"),
                ssrc=body.get("ssrc"),
                start=body.get("start"),
                end=body.get("end")
            )
        )

        aggregator_logger.debug(f"Talking section for call ID '{body.get('call_id')}' and SSRC '{body.get('ssrc')}' has been stored in db")

        broadcast_log(f"Talking Section {body.get('call_id')}:", f"Type: {body.get('type')}, Call ID: {body.get('call_id')}, SSRC: {body.get('ssrc')}, Start: {body.get('start')}, End: {body.get('end')}")


#===================================
#         Helper Functions
#===================================

    def get_participant(self, body):
        """
        Retrieves or creates a participant in the call buffer based on the provided body.
        :param body: The body of the message containing call ID and user information.
        :return: ParticipantInfo object for the user in the call.
        """
        call_info = self._call_buffer[body.get("call_id")]

        participant = next((p for p in call_info.participants if p.user == body.get("user")), None)

        if not participant:
            participant = ParticipantInfo(user=body.get("user"))
            call_info.participants.append(participant)
            aggregator_logger.debug(
                f"Aggregator: New participant {body.get('user')} added to call_id {body.get('call_id')}")

        return participant

    def _store(self, call_id: str):
        """
        Checks if the call information is complete and stores it in the database.
        :param call_id: The ID of the call to check and store.
        """
        call_info = self._call_buffer.get(call_id)
        if not call_info or not call_info.ack_received:
            return

        complete = True
        for participant in call_info.participants:
            if None in (
                    participant.ip_address,
                    participant.media_port,
                    participant.mime_type,
                    participant.server_ip,
                    participant.server_port
            ):
                complete = False
                break

        if not complete:
            return

        store_call_start(call_id, call_info)
        self._call_buffer[call_id].stored = True

        #Safety mechanism: if aggregator_ack() and aggregator_ssrc() are processed
        # simultaneously, in the worst case ssrc may never be saved.
        for participant in call_info.participants:
            if participant.ssrc:
                store_ssrc(call_id, participant.ssrc, participant.user)
