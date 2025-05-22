import threading


class Buffer:
    """
    Buffer class to handle packets for a specific SSRC.
    """

    def __init__(self, ssrc: str, buffer_size: int):
        self.ssrc = ssrc
        self.buffer_size = buffer_size
        self.buffer: list = []
        self.lock = threading.Lock()

    def add(self, packet):
        """
        Add a packet to the buffer.
        """
        with self.lock:
            self.buffer.append(packet)

    def get(self):
        """
        Retrieving data from the buffer for a certain number of packets
        """
        with self.lock:
            data = self.buffer[:self.buffer_size]
            self.buffer = self.buffer[self.buffer_size:]
            return data

    def flush(self):
        """
        Flush the buffer and return all data.
        """
        with self.lock:
            data = self.buffer[:]
            self.buffer.clear()
            return data

    def buffer_size_reached(self):
        """
        Check if the buffer size has been reached.
        """
        with self.lock:
            return len(self.buffer) >= self.buffer_size

    def size(self):
        """
        Get the current size of the buffer.
        """
        with self.lock:
            return len(self.buffer)


    def clear(self):
        """
        Clear the buffer.
        """
        with self.lock:
            self.buffer.clear()