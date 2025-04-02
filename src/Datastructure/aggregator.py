from Datastructure.dataclass import CallInfo, ParticipantInfo, EventType, Info
from typing import List, Dict
from my_logging.log_config import app_logger


class Aggregator:
    def __init__(self, eventbus):
        self.eventbus = eventbus
        self._call_buffer: Dict[str, CallInfo] = {}

        eventbus.subscribe(EventType.NEW_CALL, self.aggregator_new_call)
        eventbus.subscribe(EventType.PARTICIPANTS, self.aggregator_participation)
        eventbus.subscribe(EventType.CALL_STARTED, self.aggregator_call_start)
        eventbus.subscribe(EventType.CALL_END, self.aggregator_call_end)

        app_logger.debug("Starting Aggregator")



    def aggregator_new_call(self, event):
        # store in the buffer
        self._call_buffer[event.call_id] = CallInfo()


    def aggregator_participation(self, event):
        # store in the buffer
        self._call_buffer[event.call_id].participants.append(
            ParticipantInfo(
                user= event.user,
                media_port=event.media_port,
                mime_type=event.mime_type,
            )
        )
        print(self._call_buffer[event.call_id])


    def aggregator_call_start(self, event):
        # send message to init the call (main)
        participants = self._call_buffer[event.call_id].participants
        self.eventbus.publish(
            Info(
                type=EventType.CALL_INIT,
                call_id=event.call_id,
                amount_participant= len(participants),
                participants= participants,
            )
        )

        self._call_buffer[event.call_id].start_time = event.start_time
        print(self._call_buffer[event.call_id])

        # TODO call to api to API

        # save to the database
        self.store_in_db()



    def aggregator_call_end(self, event):
        # save directly in the database
        # TODO End Info to API
        self._call_buffer[event.call_id].end_time = event.end_time
        print(self._call_buffer[event.call_id])


        self.store_in_db()


    def store_in_db(self):
        # TODO implement the database
        pass


