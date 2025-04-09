from Datastructure.dataclass import CallInfo, ParticipantInfo, EventType, Info
from typing import List, Dict
from my_logging.log_config import app_logger, aggregator_logger


class Aggregator:
    def __init__(self, eventbus):
        self.eventbus = eventbus
        self._call_buffer: Dict[str, CallInfo] = {}

        eventbus.subscribe(EventType.NEW_CALL, self.aggregator_new_call)
        eventbus.subscribe(EventType.PARTICIPANTS, self.aggregator_participation)
        eventbus.subscribe(EventType.ACK, self.aggregator_ack)
        eventbus.subscribe(EventType.CALL_END, self.aggregator_call_end)
        eventbus.subscribe(EventType.CALL_DECLINE, self.aggregator_call_decline)

        app_logger.debug("Starting Aggregator")



    def aggregator_new_call(self, event):
        # store in the buffer
        self._call_buffer[event.call_id] = CallInfo()
        aggregator_logger.debug(f"New call is temporarily saved: '{event.call_id}'")


    def aggregator_participation(self, event):
        # store in the buffer
        self._call_buffer[event.call_id].participants.append(
            ParticipantInfo(
                user= event.user,
                media_port=event.media_port,
                mime_type=event.mime_type,
            )
        )
        aggregator_logger.debug(f"Participant {event.user} is temporarily saved in call id {event.call_id}")

        print(self._call_buffer[event.call_id])


    def aggregator_ack(self, event):
        # send message to init the call (main)

        # if call is not in self._call_bugger, then the call is canceled
        if event.call_id not in self._call_buffer:
            return


        participants = self._call_buffer[event.call_id].participants
        self.eventbus.publish(
            Info(
                type=EventType.CALL_INIT,
                call_id=event.call_id,
                amount_participant= len(participants),
                participants= participants,
            )
        )
        app_logger.debug(f"Publish information to initialising for call id '{event.call_id}'")

        self._call_buffer[event.call_id].start_time = event.start_time
        print(self._call_buffer[event.call_id])

        # TODO call to api to API

        # save to the database
        self.store_in_db()
        aggregator_logger.info(f"Call ID '{event.call_id}' has been stored in db")



    def aggregator_call_end(self, event):
        # save directly in the database
        # TODO End Info to API
        self._call_buffer[event.call_id].end_time = event.end_time
        print(self._call_buffer[event.call_id])


        self.store_in_db()
        aggregator_logger.info(f"Call ID '{event.call_id}' has been finished and stored in db")


    def aggregator_call_decline(self, event):
        # save directly in the database
        # TODO End Info to API

        remove_call_id = self._call_buffer.pop(event.call_id, None)
        if remove_call_id is not None:
            print(f"Removing call id '{event.call_id}'")

            aggregator_logger.info(f"Call ID '{event.call_id}' has been declined")

    def store_in_db(self):
        # TODO implement the database
        pass


