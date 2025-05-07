import os

from my_logging.log_config import app_logger


def validate_file(file_path) -> bool:
    # check if the file is reachable
    if not os.path.isfile(file_path) and not os.access(file_path, os.R_OK):
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