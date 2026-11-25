import io
import json
import shutil
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock
import queue
import os
from data_collection.capture_provider import CaptureProvider


class TestCaptureProvider(unittest.TestCase):
    def setUp(self):
        self.queue = queue.Queue()

    @staticmethod
    def create_mock_packet():
        """ Create mock packets for testing."""
        return [
            {"_source": {"layers": {"sip": {"sip.Method": "INVITE"}}}},
            {"_source": {"layers": {"sip": {"sip.Method": "ACK"}}}},
            {"_source": {"layers": {"rtp": {"rtp.ssrc": "0x12345678"}}}},
            {"_source": {"layers": {"rtp": {"rtp.ssrc": "0xabcdefgh"}}}},
        ]

    def validate_packet(self):
        """ Validate the packets in the queue."""
        self.assertEqual(4, self.queue.qsize())

        packets = list(self.queue.queue)

        self.assertEqual(packets[0]["_source"]["layers"]["sip"]["sip.Method"], "INVITE")
        self.assertEqual(packets[1]["_source"]["layers"]["sip"]["sip.Method"], "ACK")
        self.assertEqual(packets[2]["_source"]["layers"]["rtp"]["rtp.ssrc"], "0x12345678")
        self.assertEqual(packets[3]["_source"]["layers"]["rtp"]["rtp.ssrc"], "0xabcdefgh")

    @patch("data_collection.capture_provider.subprocess.check_output")
    @patch("os.path.exists")
    @patch("os.path.isfile")
    @patch("data_collection.capture_provider.validate_file")
    def test_file_capture(self, mock_validate_file, mock_is_file, mock_exists, mock_check_output):
        """ Test the file capture functionality of CaptureProvider."""
        # Mock the function to return True
        mock_validate_file.return_value = True
        mock_exists.return_value = True
        mock_is_file.return_value = True

        # Mock the output of TShark command
        mock_json_output = json.dumps(self.create_mock_packet())
        mock_check_output.return_value = mock_json_output

        # Create an instance of CaptureProvider with file capture
        capture_provider = CaptureProvider("file", "dummy.pcap", self.queue)
        capture_provider.file_capture("(sip or rtp)")

        # Validate the packets in the queue
        self.validate_packet()

    @patch("data_collection.capture_provider.subprocess.Popen")
    def test_live_capture(self, mock_popen):
        """ Test the live capture functionality of CaptureProvider."""
        mock_packets = self.create_mock_packet()
        lines = [json.dumps(pkt) + "\n" for pkt in mock_packets]

        # Mock the subprocess.Popen to simulate TShark output
        mock_proc = MagicMock()
        mock_proc.stdout = iter(lines)
        # Mock the poll method to simulate the process being alive until all lines are read
        mock_proc.poll.side_effect = [None] * len(lines) + [1]
        mock_proc.terminate = MagicMock()
        mock_proc.wait = MagicMock()
        mock_popen.return_value = mock_proc

        # Create an instance of CaptureProvider with live capture
        cp = CaptureProvider("live", "eth0", self.queue)
        cp.live_capture("(sip or rtp)")

        # validate the packets in the queue
        self.validate_packet()

    @patch.object(CaptureProvider, "file_capture")
    @patch.object(CaptureProvider, "live_capture")
    def test_run_method(self, mock_live_capture, mock_file_capture):
        """ Test the run method of CaptureProvider."""
        # start the live capture
        live_capture = CaptureProvider("live", "eth0", self.queue)
        live_capture.run()

        # check if the live capture method was called
        mock_live_capture.assert_called_once_with("(sip or rtp)")
        mock_file_capture.assert_not_called()

        # reset mocks
        mock_live_capture.reset_mock()
        mock_file_capture.reset_mock()

        # start the file capture
        file_capture = CaptureProvider("file", "test.pcap", self.queue)
        file_capture.run()

        # check if the file capture method was called
        mock_file_capture.assert_called_once_with("(sip or rtp)")
        mock_live_capture.assert_not_called()

class TestCaptureIntegration(unittest.TestCase):
    def setUp(self):
        self.queue = queue.Queue()
        # the sample pcapng file contains 6x SIP and 8x RTP packets --> view with Wireshark
        self.data_dir = os.path.join(os.path.join(Path(__file__).parent, "data"))
        self.file = os.path.join(self.data_dir, "test_capture_provider_samples.pcapng")

    def test_file_capture_integration(self):
        """Test the integration of CaptureProvider with a sample pcapng file."""

        if not os.path.exists(self.file):
            self.skipTest(f"Sample capture {self.file} is not available.")

        # Copy the file to a temporary location for testing because capture_provider delete the file after processing
        test_copy = os.path.join(self.data_dir, "temp_file.pcapng")
        shutil.copy(self.file, test_copy)

        # Create an instance of CaptureProvider with file capture and process the file
        capture_provider = CaptureProvider("file", test_copy, self.queue)
        capture_provider.start()
        time.sleep(2)
        capture_provider.stop()
        capture_provider.join()

        self.assertEqual(self.queue.qsize(), 14)

        # sorting the packets in the queue
        packets = list(self.queue.queue)
        sip_list = [pkt for pkt in packets if "sip" in pkt.get("_source", {}).get("layers", {})]
        rtp_list = [pkt for pkt in packets if "rtp" in pkt.get("_source", {}).get("layers", {})]

        # Validate the number of SIP and RTP packets
        self.assertEqual(len(sip_list), 6)
        self.assertEqual(len(rtp_list), 8)

    def test_live_capture_integration(self):
        """Test the integration of CaptureProvider with live capture."""
        print("This test requires a live network interface and is not suitable for automated testing.")
