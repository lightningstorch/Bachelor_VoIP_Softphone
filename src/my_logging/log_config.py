import logging
import os

"""
This module configures the loggers for the application.

Three loggers are set up:
- app_logger: Logs general application events.
- eventbus_logger: Logs events from the event bus, which is stored separately from app_logger.
- aggregator_logger: Logs events from the aggregator component, also separately 
 from app_logger.

All loggers use the same format ('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
and write to individual log files in the LOGS_DIR directory.
"""

LOGS_DIR = '../logs'
os.makedirs(LOGS_DIR, exist_ok=True)

logging_format = app_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')


# --------------------------------
# Configuration of the App-Loggers
# --------------------------------
app_logger = logging.getLogger('app')
app_logger.setLevel(logging.DEBUG)

if not app_logger.handlers:
    app_file_handler = logging.FileHandler(os.path.join(LOGS_DIR, 'app.log'))
    app_file_handler.setLevel(logging.DEBUG)
    app_file_handler.setFormatter(logging_format)

    app_logger.addHandler(app_file_handler)

# -------------------------------------
# Configuration of the EventBus-Loggers
# -------------------------------------
message_service_logger = logging.getLogger('message_service')
message_service_logger.setLevel(logging.DEBUG)

if not message_service_logger.handlers:
    message_service_file_handler = logging.FileHandler(os.path.join(LOGS_DIR, 'message_service.log'))
    message_service_file_handler.setLevel(logging.DEBUG)
    message_service_file_handler.setFormatter(logging_format)

    message_service_logger.addHandler(message_service_file_handler)
    # Important: Deactivate propagation so that these logs do not also end up in app.log
    message_service_logger.propagate = False

# -------------------------------------
# Configuration of the Aggregator-Loggers
# -------------------------------------
aggregator_logger = logging.getLogger('aggregator')
aggregator_logger.setLevel(logging.DEBUG)

if not aggregator_logger.handlers:
    aggregator_file_handler = logging.FileHandler(os.path.join(LOGS_DIR, 'aggregator.log'))
    aggregator_file_handler.setLevel(logging.DEBUG)
    aggregator_file_handler.setFormatter(logging_format)

    aggregator_logger.addHandler(aggregator_file_handler)
    # Important: Deactivate propagation so that these logs do not also end up in app.log
    aggregator_logger.propagate = False

