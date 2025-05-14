import asyncio
import json

from aio_pika import IncomingMessage, ExchangeType
from datastructure.database.database import Session
from datastructure.database.models import Calls
from datastructure.dataclass_models import CallInfo, ParticipantInfo, EventType, Info
from typing import Dict
from my_logging.log_config import app_logger, aggregator_logger


class Aggregator:
    def __init__(self, message_service):
        self.message_service = message_service
        self._call_buffer: Dict[str, CallInfo] = {}

        self.message_service.subscribe(self.aggregator_new_call, "NEW_CALL", ExchangeType.DIRECT, "aggregator_new_call_queue", "new_call").result(timeout=5)
        self.message_service.subscribe(self.aggregator_participation, "PARTICIPANTS", ExchangeType.DIRECT, "aggregator_participation_queue", "participation").result(timeout=5)
        self.message_service.subscribe(self.aggregator_ack, "ACK", ExchangeType.DIRECT, "aggregator_ack_queue", "ack").result(timeout=5)
        self.message_service.subscribe(self.aggregator_call_end, "CALL_END", ExchangeType.DIRECT, "aggregator_call_end_queue", "end_call").result(timeout=5)
        self.message_service.subscribe(self.aggregator_call_decline, "CALL_DECLINE", ExchangeType.DIRECT, "aggregator_call_decline_queue", "call_decline").result(timeout=5)


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

        # store in the buffer
        if body.get("call_id") in self._call_buffer:
            self._call_buffer[body.get("call_id")].participants.append(
                ParticipantInfo(
                    user= body.get("user"),
                    media_port=body.get("media_port"),
                    mime_type=body.get("mime_type"),
                )
            )

            aggregator_logger.debug(f"Aggregator: Participant {body.get("user")} is temporarily saved in call_id {body.get("call_id")}")
            print(f"Aggregator: Buffer: {self._call_buffer[body.get("call_id")]}")
        else:
            aggregator_logger.warning(f"Aggregator: Call ID {body.get('call_id')} not found in buffer")

    def aggregator_ack(self, message: IncomingMessage):
        # confirm receipt of the message
        asyncio.create_task(message.ack())
        body = json.loads(message.body.decode())

        # Call was not answered -> Call decline
        if body.get("call_id") not in self._call_buffer:
            return

        # send a message to init the call (main)
        participants = self._call_buffer[body.get("call_id")].participants
        payload = Info(
                type=EventType.CALL_INIT,
                call_id=body.get("call_id"),
                amount_participant= len(participants),
                participants= participants,
            ).model_dump_json()

        self.message_service.publish(
            payload,
            exchange_name="INIT_CALL",
            exchange_type=ExchangeType.DIRECT,
        )

        app_logger.debug(f"Publish information to initialising for call id '{body.get("call_id")}'")

        self._call_buffer[body.get("call_id")].start_time = body.get("start_time")
        print(f"Aggregator: Buffer: {self._call_buffer[body.get("call_id")]}")

        # TODO call to api to API

        # save to the database
        #self._store_in_db(event.call_id)
        aggregator_logger.debug(f"Call ID '{body.get("call_id")}' has been stored in db")


    # TODO check if it works
    def aggregator_call_end(self, message: IncomingMessage):
        # confirm receipt of the message
        asyncio.create_task(message.ack())
        body = json.loads(message.body.decode())

        # save directly in the database
        self._call_buffer[body.get("call_id")].end_time = body.get("end_time")
        print(self._call_buffer[body.get("call_id")])

        # delete the element in the buffer and save it to the database
        call_info = self._call_buffer.pop(body.get("call_id"))
        # TODO Integration Database
        #self._store_in_db(body.get("call_id"), call_info)

        aggregator_logger.info(f"Call ID '{body.get("call_id")}' has been finished and stored in db")
        print(f"Aggregator: Call ID '{body.get("call_id")}' has been finished and stored in db")


    # TODO check if it works
    def aggregator_call_decline(self, message: IncomingMessage):
        # confirm receipt of the message
        asyncio.create_task(message.ack())
        body = json.loads(message.body.decode())

        # removed because the call is decline
        remove_call_id = self._call_buffer.pop(body.get("call_id"))
        if remove_call_id is not None:
            print(f"Removing call id '{body.get("call_id")}'")
            aggregator_logger.info(f"Call ID '{body.get("call_id")}' has been declined")


    # TODO implement the database
    def _store_in_db(self, call_id: str, call_info: CallInfo):

        session = Session()

        db_call = session.query(Calls).get(call_id)
        buffer_call = self._call_buffer[call_id]

        # inizialise the session

        # prepare the element for storing

        # store the element in the database









