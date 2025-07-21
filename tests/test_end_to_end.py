import os
import shutil
import time
import unittest
from pathlib import Path
from queue import Queue
from unittest.mock import patch

class TestEndToEnd(unittest.TestCase):
    """
    This test was developed to compare real pcap files that were documented during
    the recording with Wireshark. The comparisons concern the participants and the
    talking_sections, whereby the talking_sections are compared with a tolerance.
    As the tests take some time to run, it is recommended to run the tests separately
    and not together. It can happen that when the entire class is executed, the tests
    get stuck in an endless loop.
    """

    def setUp(self):
        self.data_dir = os.path.join(Path(__file__).parent, "data")

        if os.path.exists(os.path.join(Path(__file__).parent, "app.db")):
            os.remove(os.path.join(Path(__file__).parent, "app.db"))

        self.queue_packets = Queue()
        self.cleanup_queue = Queue()

        from datastructure.database.database import init_db
        init_db()

        from datastructure.async_message_service import get_message_service
        from call_context.manager_call_context import ManagerCallContext
        from datastructure.aggregator import Aggregator

        self.message_service = get_message_service()
        self.manager_call_context = ManagerCallContext(self.message_service, self.cleanup_queue)
        self.aggregator = Aggregator(self.message_service)

        self.comp_tolerance = 4  # +- 2 seconds for comparison

    def tearDown(self):
        # Shutdown call contexts
        self.manager_call_context.shutdown_all_calls()
        # Close message service
        self.message_service.close()

    def test_audio_validation_1(self):
        file_name = "test_Audio-Validation-1.pcapng"

        call_sections = {
            "call_id": "3jXyt6KehE",
            "participants": [
                {"user": "linphpne1", "ip_address": "192.168.0.55"},
                {"user": "Linphone2", "ip_address": "192.168.0.56"}
            ],
            "talking_sections": [
                {"section_start": 45, "section_end": 55, "type": "speech"},
                {"section_start": 65, "section_end": 75, "type": "speech"},
                {"section_start": 10, "section_end": 30, "type": "speech"},
                {"section_start": 90, "section_end": 120, "type": "speech"},
            ]
        }

        self.process_file(file_name, call_sections)

    def test_audio_validation_2(self):
        file_name = "test_Audio-Validation-2.pcapng"

        call_sections = {
            "call_id": "utv-kqzvFZ",
            "participants": [
                {"user": "linphpne1", "ip_address": "192.168.0.55"},
                {"user": "Linphone2", "ip_address": "192.168.0.56"}
            ],
            "talking_sections": [
                {"section_start": 22, "section_end": 57, "type": "speech"},
                {"section_start": 65, "section_end": 80, "type": "speech"},
            ]
        }

        self.process_file(file_name, call_sections)

    def test_audio_validation_3(self):
        file_name = "test_Audio-Validation-3.pcapng"

        call_sections = {
            "call_id": "JYe-ONYdyQ",
            "participants": [
                {"user": "linphpne1", "ip_address": "192.168.0.55"},
                {"user": "linphone2", "ip_address": "192.168.0.56"}
            ],
            "talking_sections": [
                {"section_start": 2, "section_end": 32, "type": "speech"},
                {"section_start": 85, "section_end": 110, "type": "speech"},
                {"section_start": 50, "section_end": 75, "type": "speech"},
            ]
        }

        self.process_file(file_name, call_sections)

    def process_file(self, file_name, call_sections):
        """Process a pcap file and check the data in the database."""
        from datastructure.database.database import get_call_by_id
        from data_collection.capture_provider import CaptureProvider
        from data_collection.packet_processor import PacketProcessor

        # a copy is needed because the CaptureProvider will delete the file after processing
        test_file = os.path.join(self.data_dir, file_name)
        test_file = self.copy_file(test_file)

        # Start capture provider to process the pcap file - use positional arguments
        capture_provider = CaptureProvider(
            "file",
            test_file,
            self.queue_packets
        )
        capture_provider.start()

        # Initialize packet processor
        packet_processor = PacketProcessor(
            self.message_service,
            self.queue_packets,
            self.manager_call_context,
            self.cleanup_queue
        )
        packet_processor.start()

        self._waiting_for_call_end(call_sections["call_id"])

        # Stop components
        capture_provider.stop()
        capture_provider.join()
        packet_processor.stop()
        packet_processor.join()

        calls = get_call_by_id(call_sections["call_id"])

        self._check_data(calls, call_sections)


    #==================================
    #         Helper methods
    #==================================

    def copy_file(self, file_path):
        """Utility method to copy a file to the data directory."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Test file {file_path} does not exist.")

        file_copy = os.path.join(self.data_dir, "temp_file.pcapng")
        shutil.copy(file_path, file_copy)

        return file_copy

    @staticmethod
    def _waiting_for_call_end(call_id):
        """Helper method to wait for a call to end."""
        from datastructure.database.database import get_call_by_id
        while True:
            call = get_call_by_id(call_id)
            if call is not None and call.end_time is not None:
                break
            time.sleep(1)

    def _check_data(self, calls, call_sections):
        """Check if the data in the database matches the expected data."""
        self.assertIsNotNone(calls, "No calls found in database after processing")

        db_participants = [
            {"user": p.user.lower(), "ip_address": p.ip_address}
            for p in calls.participants
        ]

        db_talking_sections = [
            {"section_start": ts.section_start, "section_end": ts.section_end, "type": ts.type}
            for ts in calls.talking_sections
        ]

        expected_participants = [
            {"user": p["user"].lower(), "ip_address": p["ip_address"]}
            for p in call_sections["participants"]
        ]

        self.assertEqual(
            len(db_participants),
            len(expected_participants),
            "Participants in the database do not match expected participants - checked with the length"
        )

        for expected_participant in expected_participants:
            self.assertTrue(
                any(expected_participant["user"] == p["user"] and
                    expected_participant["ip_address"] == p["ip_address"]
                    for p in db_participants),
                f"Expected participant {expected_participant} not found in database"
            )

        expected_talking_sections = [
            {"section_start": p["section_start"], "section_end": p["section_end"], "type": p["type"]}
            for p in call_sections["talking_sections"]
        ]

        # check if the number of talking sections in the database matches the expected number
        self.assertEqual(
            len(db_talking_sections),
            len(expected_talking_sections),
            "Not enough speech sections found in database"
        )

        for expected_ts in expected_talking_sections:
            # Check if at least one database section matches this expected section with tolerance +- 2 seconds
            self.assertTrue(
                any(abs(db_ts["section_start"] - expected_ts["section_start"]) < self.comp_tolerance and
                    abs(db_ts["section_end"] - expected_ts["section_end"]) < self.comp_tolerance
                    for db_ts in db_talking_sections),
                f"Expected talking section {expected_ts} not found in database (with 5 second tolerance)"
            )