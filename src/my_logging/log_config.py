import logging
import os

from config.config import app_log_level, message_service_log_level, aggregator_log_level, call_context_log_level, \
    database_log_level

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

def _get_log_level(level_str):
    try:
        return getattr(logging, level_str.upper())
    except AttributeError:
        raise ValueError(f"Invalid log level: {level_str}")

LOGS_DIR = '../logs'
os.makedirs(LOGS_DIR, exist_ok=True)

logging_format = app_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')


# --------------------------------
# Configuration of the App-Loggers
# --------------------------------
app_logger = logging.getLogger('app')
app_logger.setLevel(_get_log_level(app_log_level))

if not app_logger.handlers:
    app_file_handler = logging.FileHandler(os.path.join(LOGS_DIR, 'app.log'))
    app_file_handler.setLevel(_get_log_level(app_log_level))
    app_file_handler.setFormatter(logging_format)

    app_logger.addHandler(app_file_handler)

# -------------------------------------
# Configuration of the Message-Service-Loggers
# -------------------------------------
message_service_logger = logging.getLogger('message_service')
message_service_logger.setLevel(_get_log_level(message_service_log_level))

if not message_service_logger.handlers:
    message_service_file_handler = logging.FileHandler(os.path.join(LOGS_DIR, 'message_service.log'))
    message_service_file_handler.setLevel(_get_log_level(message_service_log_level))
    message_service_file_handler.setFormatter(logging_format)

    message_service_logger.addHandler(message_service_file_handler)
    # Important: Deactivate propagation so that these logs do not also end up in app.log
    message_service_logger.propagate = False

# -------------------------------------
# Configuration of the Aggregator-Loggers
# -------------------------------------
aggregator_logger = logging.getLogger('aggregator')
aggregator_logger.setLevel(_get_log_level(aggregator_log_level))

if not aggregator_logger.handlers:
    aggregator_file_handler = logging.FileHandler(os.path.join(LOGS_DIR, 'aggregator.log'))
    aggregator_file_handler.setLevel(_get_log_level(aggregator_log_level))
    aggregator_file_handler.setFormatter(logging_format)

    aggregator_logger.addHandler(aggregator_file_handler)
    # Important: Deactivate propagation so that these logs do not also end up in app.log
    aggregator_logger.propagate = False

# -------------------------------------
# Configuration of the Call_Context-Loggers
# -------------------------------------
call_context_logger = logging.getLogger('call_context')
call_context_logger.setLevel(_get_log_level(call_context_log_level))

if not call_context_logger.handlers:
    call_context_file_handler = logging.FileHandler(os.path.join(LOGS_DIR, 'call_context.log'))
    call_context_file_handler.setLevel(_get_log_level(call_context_log_level))
    call_context_file_handler.setFormatter(logging_format)

    call_context_logger.addHandler(call_context_file_handler)
    # Important: Deactivate propagation so that these logs do not also end up in app.log
    call_context_logger.propagate = False


# -------------------------------------
# Configuration of the Database-Loggers
# -------------------------------------
database_logger = logging.getLogger('database')
database_logger.setLevel(_get_log_level(database_log_level))

if not database_logger.handlers:
    database_file_handler = logging.FileHandler(os.path.join(LOGS_DIR, 'database.log'))
    database_file_handler.setLevel(_get_log_level(database_log_level))
    database_file_handler.setFormatter(logging_format)

    database_logger.addHandler(database_file_handler)
    # Important: Deactivate propagation so that these logs do not also end up in app.log
    database_logger.propagate = False

