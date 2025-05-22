import asyncio
import json
from datetime import datetime

from aio_pika import IncomingMessage, ExchangeType
from datastructure.database.database import Session, store_call_start, store_call_end, store_ssrc
from datastructure.database.models import Calls, Participants
from datastructure.dataclass_models import CallInfo, ParticipantInfo, EventType, Info
from typing import Dict
from my_logging.log_config import app_logger, aggregator_logger


class Aggregator:
    def __init__(self, message_service):
        self.message_service = message_service
        self._call_buffer: Dict[str, CallInfo] = {}

        self.message_service.subscribe(self.aggregator_new_call, "NEW_CALL", ExchangeType.DIRECT, "aggregator_new_call_queue", "new_call").result(timeout=5)
        self.message_service.subscribe(self.aggregator_participation, "PARTICIPANTS", ExchangeType.DIRECT, "aggregator_participation_queue", "participation").result(timeout=5)
        self.message_service.subscribe(self.aggregator_participation, "SERVER_INFO", ExchangeType.DIRECT, "aggregator_server_data_queue", "server_info").result(timeout=5)
        self.message_service.subscribe(self.aggregator_ack, "ACK", ExchangeType.DIRECT, "aggregator_ack_queue", "ack").result(timeout=5)
        self.message_service.subscribe(self.aggregator_call_end, "CALL_END", ExchangeType.DIRECT, "aggregator_call_end_queue", "end_call").result(timeout=5)
        self.message_service.subscribe(self.aggregator_call_decline, "CALL_DECLINE", ExchangeType.DIRECT, "aggregator_call_decline_queue", "call_decline").result(timeout=5)
        self.message_service.subscribe(self.aggregator_ssrc, "SSRC", ExchangeType.DIRECT, "aggregator_ssrc_queue", "ssrc").result(timeout=5)

        app_logger.debug("Aggregator: Starting Aggregator")


    def aggregator_new_call(self, message: IncomingMessage):
        # confirm receipt of the message
        asyncio.create_task(message.ack())
        body = json.loads(message.body.decode())

        # store in the buffer
        self._call_buffer[body.get("call_id")] = CallInfo()

        print(f"Aggregator: New call is temporarily saved: '{body.get('call_id')}'")
        aggregator_logger.debug(f"Aggregator: New call is temporarily saved: '{body.get('call_id')}'")

    def aggregator_participation(self, message: IncomingMessage):
        # confirm receipt of the message
        asyncio.create_task(message.ack())
        body = json.loads(message.body.decode())

        if body.get('call_id') not in self._call_buffer:
            aggregator_logger.warning(f"Aggregator: Call ID {body.get('call_id')} not found in buffer")
            return

        fields = {}
        if "ip_address" in body:
            fields["ip_address"] = body["ip_address"]
        if "media_port" in body:
            fields["media_port"] = int(body["media_port"])
        if "mime_type" in body:
            fields["mime_type"] = body["mime_type"]
        if "server_ip" in body:
            fields["server_ip"] = body["server_ip"]
        if "server_port" in body:
            fields["server_port"] = int(body["server_port"])

        call_info = self._call_buffer[body.get("call_id")]

        participant = next((p for p in call_info.participants if p.user == body.get("user")), None)

        if not participant:
            # Update the server IP and port for the participant
            participant = ParticipantInfo(user = body.get("user"))
            call_info.participants.append(participant)
            aggregator_logger.debug(f"Aggregator: New participant {body.get('user')} added to call_id {body.get('call_id')}")

        for key, value in fields.items():
            setattr(participant, key, value)

        aggregator_logger.debug(f"Aggregator: Participant {body.get('user')} updated with all fields for call_id {body.get('call_id')}")

    def aggregator_ack(self, message: IncomingMessage):
        # confirm receipt of the message
        asyncio.create_task(message.ack())
        body = json.loads(message.body.decode())

        # Call was not answered -> Call decline
        if body.get("call_id") not in self._call_buffer:
            return

        app_logger.debug(f"Publish information to initialising for call id '{body.get("call_id")}'")

        self._call_buffer[body.get("call_id")].start_time = datetime.fromisoformat(body.get("start_time"))
        print(f"Aggregator: Buffer: {self._call_buffer[body.get("call_id")]}")

        # TODO call to api to API

        # save to the database
        call_info = self._call_buffer.get(body.get("call_id"))
        store_call_start(body.get("call_id"), call_info)
        aggregator_logger.debug(f"Call ID '{body.get("call_id")}' has been stored in db")

    def aggregator_call_end(self, message: IncomingMessage):
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
        print(f"Aggregator: Call ID '{body.get("call_id")}' has been finished and stored in db")

    def aggregator_call_decline(self, message: IncomingMessage):
        # confirm receipt of the message
        asyncio.create_task(message.ack())
        body = json.loads(message.body.decode())

        # removed because the call is decline
        remove_call_id = self._call_buffer.pop(body.get("call_id"))
        if remove_call_id is not None:
            print(f"Removing call id '{body.get("call_id")}'")
            aggregator_logger.info(f"Call ID '{body.get("call_id")}' has been declined")

    def aggregator_ssrc(self, message: IncomingMessage):
        # confirm receipt of the message
        asyncio.create_task(message.ack())
        body = json.loads(message.body.decode())

        participant = next((p for p in self._call_buffer[body.get("call_id")].participants if p.user == body.get("user")), None)

        if participant:
            participant.ssrc = body.get("ssrc")

        store_ssrc(body.get("call_id"), body.get("ssrc"), body.get("user"))
        aggregator_logger.debug(f"SSRC '{body.get('ssrc')}' has been stored in db")

