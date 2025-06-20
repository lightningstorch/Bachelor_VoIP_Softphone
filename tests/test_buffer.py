import pytest
from analysis.buffer import Buffer

"""
Test suite for the Buffer class in the analysis module.
This suite tests the functionality of the Buffer class, including adding packets,
retrieving data, checking buffer size, and ensuring thread safety.
"""

def test_add_and_size(buffer):
    assert buffer.size() == 0

    buffer.add("packet1")
    assert buffer.size() == 1

    buffer.add("packet2")
    assert buffer.size() == 2

def test_add_and_get(buffer, fill_buffer):
    fill_buffer(2)

    data = buffer.get()
    assert data == ["packet1", "packet2"]
    assert buffer.size() == 0

    fill_buffer(4)

    data = buffer.get()
    assert data == ["packet1", "packet2", "packet3"]
    assert buffer.size() == 1  # Only "packet4" should remain in the buffer

def test_buffer_size_reached(buffer):
    assert not buffer.buffer_size_reached()

    buffer.add("packet1")
    assert not buffer.buffer_size_reached()

    buffer.add("packet2")
    assert not buffer.buffer_size_reached()

    buffer.add("packet3")
    assert buffer.buffer_size_reached()

def test_get_slice_off(buffer, fill_buffer):
    fill_buffer(5)

    data = buffer.get()
    assert data == ["packet1", "packet2", "packet3"]
    assert buffer.size() == 2

    data2 = buffer.get()
    assert data2 == ["packet4", "packet5"]
    assert buffer.size() == 0

def test_flush_clears_call(buffer, fill_buffer):
    fill_buffer(2)

    data = buffer.flush()
    assert data == ["packet1", "packet2"]
    assert buffer.size() == 0

    # Ensure that the buffer is empty after flushing
    assert buffer.flush() == []

def test_clear(buffer, fill_buffer):
    fill_buffer(3)

    buffer.clear()
    assert buffer.size() == 0
    assert buffer.flush() == []  # Ensure flush also returns an empty list after clearing

def test_thread_safety(buffer, fill_buffer):
    """
    Test that the buffer can handle concurrent access without issues.
    """
    import threading

    def add_packets():
        for i in range(5):
            buffer.add(f"packet{i+1}")

    threads = [threading.Thread(target=add_packets) for _ in range(10)]

    for thread in threads:
        thread.start()

    for thread in threads:
        thread.join()

    assert buffer.size() == 50  # 5 packets from each of the 10 threads

#================================================
#           Helper methods
#================================================

@pytest.fixture
def buffer():
    return Buffer(ssrc="ssrc1", buffer_size=3)

@pytest.fixture
def fill_buffer(buffer):
    """
    Helper function to fill the buffer with a specified number of packets.
    """
    def _fill(count: int):
        for i in range(count):
            buffer.add(f"packet{i+1}")
        return buffer
    return _fill
