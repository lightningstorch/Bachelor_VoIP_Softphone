from my_logging.log_config import eventbus_logger, app_logger
import queue
import threading

# TODO Integrate more logging

class EventBus:
    """
        A simple implementation of an event bus system for asynchronous communication between the components

        Properties:
             _queue (queue.Queue): A queue for incoming events.
            _subscribers (dict): Registered callback functions that respond to specific event types.
            _lock (threading.Lock): A lock for thread-safe use of the _subscribers dict to add/remove subscribers

        Methods:
            subscribe: Registers a callback for a specific event type.
            unsubscribe: Removes a registered callback.
            publish: Publishes an event and notifies subscribers.
        """

    def __init__(self):
        self._queue = queue.Queue()
        self._subscribers = {}
        self._lock = threading.Lock()
        app_logger.debug("Starting EventBus")


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
        eventbus_logger.debug(f"Subscribed: Callback {callback.__name__} for event_type '{event_type.value}'")


    def unsubscribe(self, event_type, callback):
        with self._lock:
            if event_type in self._subscribers:
                self._subscribers[event_type].remove(callback)
        eventbus_logger.debug(f"Unsubscribed: Callback {callback.__name__} for event_type '{event_type.value}'")


    def publish(self, event):
        self._queue.put(event)
        eventbus_logger.debug(f"Published: '{event}'")
        self._notify_subscriber(event)


    # the function calls only the type of the event
    def _notify_subscriber(self, event):
        """
        Calls all callback functions in self._subscribers that are registered for the event type of the given event.

        Args:
            event: Incoming event with the event type.
        """
        with self._lock:
            callbacks = self._subscribers.get(event.type, [])
        for callback in callbacks:
            try:
                callback(event)
            except Exception as e:
                app_logger.error(f"Error when executing callback {callback.__name__} for event {event}: {e}")

