import os

from data_collection.capture_provider import CaptureProvider
from data_collection.packet_processor import PacketProcessor
from my_logging.log_config import app_logger, broadcast_log


class ProgramStateManager:
    """
    Singleton class to manage the program state, including the current mode and source.
    This class ensures that only one instance exists throughout the application lifecycle.
    It provides methods to get and set the mode and source, and to switch modes if necessary.
    The mode can be either "live" or "file", and the source is a string representing
    the current data source (e.g., network interface or file path).
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ProgramStateManager, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        # Initialize only once
        if getattr(self, "_initialized", False):
            return

        self._mode = "live"    # Default mode
        self._source = None
        self._initialized = True

    def get_mode(self):
        return self._mode

    def set_mode(self, value):
        if value not in ["live", "file"]:
            raise ValueError("Mode must be either 'live' or 'file'.")
        self._mode = value

    def get_source(self):
        return self._source

    def set_source(self, value):
        self._source = value

    def switch_mode(self, mode: str, source: str):
        """
        Switches the mode and source of the program state.
        If the mode and source are already set to the desired values,
        it does nothing and returns False.
        If the mode or source is different, it updates them and returns True.
        :param mode: The mode to switch to, either "live" or "file".
        :param source: The source to switch to, either a network interface or a file path.
        :return: True if the mode or source was changed, False if they were already set to the desired values.
        """
        if mode == self._mode and source == self._source:
            app_logger.debug(f"Already in {mode} mode with source={source}, skipping.")
            broadcast_log("Info", f"Already in {mode} mode with source={os.path.basename(source)}, skipping.")
            print(f"Already in {mode} mode with source={source}, skipping start.")
            return False

        self._mode = mode
        self._source = source
        return True

