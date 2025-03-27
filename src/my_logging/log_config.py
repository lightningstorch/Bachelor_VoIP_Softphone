import logging
import os

LOGS_DIR = '../logs'
os.makedirs(LOGS_DIR, exist_ok=True)

logging_format = app_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')


# --------------------------------
# Configuration of the App-Loggers
# --------------------------------
app_logger = logging.getLogger('app')
app_logger.setLevel(logging.DEBUG)

app_file_handler = logging.FileHandler(os.path.join(LOGS_DIR, 'app.log'))
app_file_handler.setLevel(logging.DEBUG)
app_file_handler.setFormatter(logging_format)

app_logger.addHandler(app_file_handler)

# -------------------------------------
# Configuration of the EventBus-Loggers
# -------------------------------------
eventbus_logger = logging.getLogger('eventbus')
eventbus_logger.setLevel(logging.DEBUG)


eventbus_file_handler = logging.FileHandler(os.path.join(LOGS_DIR, 'eventbus.log'))
eventbus_file_handler.setLevel(logging.DEBUG)
eventbus_file_handler.setFormatter(logging_format)

eventbus_logger.addHandler(eventbus_file_handler)
# Important: Deactivate propagation so that these logs do not also end up in app.log
eventbus_logger.propagate = False



