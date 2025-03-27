from datetime import datetime

from Datastructure.dataclass import Event, EventType
from Datastructure.event_bus import EventBus
from src.my_logging.log_config import eventbus_logger, app_logger



def main():
    app_logger.info("System is starting...")

    eventbus = EventBus()

    # For test purposes
    eventbus.subscribe(EventType.NEW_CALL, handle_new_event)

    eventbus.publish(
        Event(
            type = EventType.NEW_CALL,
            call_id=101,
            start_time = datetime.now(),
        )
    )












def handle_new_event(event: Event):
    print(event)


if __name__ == '__main__':
    main()
