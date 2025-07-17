import os

from my_logging.log_config import app_logger


def validate_file(file_path) -> bool:
    """
    Validate the file to ensure it exists, is readable, and has the correct file extension.
    :param file_path: the path to the file to validate
    :return: True if the file is valid, False otherwise
    """
    # check if the file is reachable
    if not os.path.isfile(file_path) or not os.access(file_path, os.R_OK):
        app_logger.error(f"File {file_path} does not exist or is not readable")
        return False

    # check the file of the correct file extension (network dumps)
    _, ext = os.path.splitext(file_path)
    ext = ext.lower()
    allowed_extensions = ['.pcap', '.pcapng']

    if ext not in allowed_extensions:
        app_logger.error(f"File extension must be one of {allowed_extensions} and not {ext}")
        return False

    app_logger.debug(f"File is valid: {file_path}")
    return True

def call_match(buffer_call, db_call) -> bool:
    """
    Compare a call from the buffer with a call from the database to check if they match.
    :param buffer_call: the call from the buffer
    :param db_call: the call from the database
    :return: True if the calls match, False otherwise
    """
    if not db_call:
        return False

    if (
        buffer_call.caller != db_call.caller or
        buffer_call.start_time != db_call.start_time
    ):
        return False

    if len(buffer_call.participants) != len(db_call.participants):
        return False

    for participant in buffer_call.participants:
        match_found = False

        for db_participant in db_call.participants:
            if (participant.user == db_participant.user and
                participant.ip_address == db_participant.ip_address and
                participant.media_port == db_participant.media_port and
                participant.mime_type == db_participant.mime_type and
                participant.server_ip == db_participant.server_ip and
                participant.server_port == db_participant.server_port
            ):
                match_found = True
                break

        if not match_found:
            return False

    return True