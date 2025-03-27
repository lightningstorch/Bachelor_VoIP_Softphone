from src.my_logging.log_config import eventbus_logger, app_logger
import queue
import threading

# TODO Integrate more logging

class EventBus:
    def __init__(self):
        self._queue = queue.Queue()
        self._subscribers = {}
        self._lock = threading.Lock()
        app_logger.info("Starting EventBus")


    def has_event(self):
        return not self._queue.empty()

    def get_event(self):
        try:
            event = self._queue.get(block=False) # don't block
            return event
        except queue.Empty:
            return None


    def subscribe(self, event_type, callback):
        with self._lock:
            if event_type not in self._subscribers:
                self._subscribers[event_type] = []
            self._subscribers[event_type].append(callback)
        eventbus_logger.info(f"Subscribed: Callback {callback.__name__} for event_type '{event_type.value}'")


    def publish(self, event):
        self._queue.put(event)
        eventbus_logger.info(f"Published: '{event}'")
        self._notify_subscriber(event)


    def _notify_subscriber(self, event):
        with self._lock:
            callbacks = self._subscribers.get(event.type, [])
        for callback in callbacks:
            try:
                callback(event)
            except Exception as e:
                app_logger.error(f"Error when executing callback {callback.__name__} for event {event}:", e)

