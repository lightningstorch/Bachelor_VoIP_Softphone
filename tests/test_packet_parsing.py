import unittest
import datetime

from typing import OrderedDict
from utils_tests.load_file import get_sip_sample_data, get_rtp_sample_data
from utils.packet_parsing import (
    get_layer, get_preferred_codec_sample_rate, get_media_port, get_sdp_connection_info_address, get_call_id,
    get_from_user, get_to_user, get_method, get_status_code, get_cseq_method, get_status_line,
    get_time_stamp_isoformat, get_time_stamp_epoch, get_ip_src, get_ip_dst, get_udp_srcport,
    get_udp_dstport, get_ssrc, get_rtp_payload, get_opus_frame_data, get_rtp_timestamp, get_via_branches,
    handle_duplicates,
)

class TestPacketParsing(unittest.TestCase):
    def setUp(self):
        self.packet_invite = get_sip_sample_data("invite_incoming")
        self.sip_invite = get_layer(self.packet_invite, "sip")

        self.packet_200_invite = get_sip_sample_data("200_invite_incoming")
        self.sip_200_invite = get_layer(self.packet_200_invite, "sip")

        self.rtp_packets = get_rtp_sample_data()

    def test_get_layer(self):
        """Test if the get_layer function correctly retrieves the SIP layer from a packet."""
        self.assertIsInstance(self.sip_invite, dict)
        self.assertIn("sip.Request-Line", self.sip_invite)

    def test_get_preferred_codec_sample_rate(self):
        """Test if the get_preferred_codec_sample_rate function returns the correct sample rate for Opus."""
        mime_type, sample_rate = get_preferred_codec_sample_rate(self.sip_invite)
        self.assertEqual(mime_type, "opus")
        self.assertEqual(int(sample_rate), 48000)

    def test_get_media_port(self):
        """Test if the get_media_port function retrieves the correct media port from the SIP layer."""
        media_port = get_media_port(self.sip_invite)
        self.assertEqual(int(media_port), 38449)

    def test_get_sdp_connection_info_address(self):
        """Test if the get_sdp_connection_info_address function retrieves the correct connection address."""
        address = get_sdp_connection_info_address(self.sip_invite)
        self.assertEqual(address, "192.168.0.55")

    def test_get_call_id(self):
        """Test if the get_call_id function retrieves the correct Call-ID from the SIP layer."""
        call_id = get_call_id(self.sip_invite)
        self.assertEqual(call_id, "3jXyt6KehE")

    def test_get_from_user(self):
        """Test if the get_from_user function retrieves the correct user from the From header."""
        from_user = get_from_user(self.sip_invite)
        self.assertEqual(from_user, "linphpne1")

    def test_get_to_user(self):
        """Test if the get_to_user function retrieves the correct user from the To header."""
        to_user = get_to_user(self.sip_invite)
        self.assertEqual(to_user.lower(), "linphone2")

    def test_get_method(self):
        """Test if the get_method function retrieves the correct SIP method."""
        method = get_method(self.sip_invite)
        self.assertEqual(method, "INVITE")

    def test_get_status_code(self):
        """Test if the get_status_code function retrieves the correct status code from the SIP layer."""
        status_code = get_status_code(self.sip_200_invite)
        self.assertEqual(status_code, "200")

    def test_get_cseq_method(self):
        """Test if the get_cseq_method function retrieves the correct CSeq method."""
        cseq_method = get_cseq_method(self.sip_200_invite)
        self.assertEqual(cseq_method, "INVITE")

    def test_get_status_line(self):
        """Test if the get_status_line function retrieves the correct status line from the SIP layer."""
        status_line = get_status_line(self.sip_200_invite)
        self.assertEqual(status_line, "SIP/2.0 200 Ok")

    def test_get_time_stamp_isoformat(self):
        """Test if the get_time_stamp_isoformat function returns the correct ISO format timestamp."""
        timestamp = get_time_stamp_isoformat(self.packet_invite)
        expected_timestamp = datetime.datetime(2025, 6, 5, 17, 31, 48, 208215).isoformat()
        self.assertEqual(timestamp, expected_timestamp)

    def test_get_time_stamp_epoch(self):
        """Test if the get_time_stamp_epoch function returns the correct epoch timestamp."""
        epoch_timestamp = get_time_stamp_epoch(self.packet_invite)
        expected_epoch = 1749137508.208215000
        self.assertEqual(epoch_timestamp, expected_epoch)

    def test_get_ip_src(self):
        """Test if the get_ip_src function retrieves the correct source IP address."""
        ip_src = get_ip_src(self.packet_invite)
        self.assertEqual(ip_src, "192.168.0.55")

    def test_get_ip_dst(self):
        """Test if the get_ip_dst function retrieves the correct destination IP address."""
        ip_dst = get_ip_dst(self.packet_invite)
        self.assertEqual(ip_dst, "192.168.0.63")

    def test_get_udp_srcport(self):
        """Test if the get_udp_srcport function retrieves the correct source UDP port."""
        udp_srcport = get_udp_srcport(self.packet_invite)
        self.assertEqual(int(udp_srcport), 52082)

    def test_get_udp_dstport(self):
        """Test if the get_udp_dstport function retrieves the correct destination UDP port."""
        udp_dstport = get_udp_dstport(self.packet_invite)
        self.assertEqual(int(udp_dstport), 5060)

    def test_get_ssrc(self):
        """Test if the get_ssrc function retrieves the correct SSRC from RTP packets."""
        ssrc = get_ssrc(self.rtp_packets)
        self.assertEqual(ssrc, "0x30a8e9fe")

    def test_get_rtp_payload(self):
        """Test if the get_rtp_payload function retrieves the correct RTP payload."""
        rtp_payload = get_rtp_payload(self.rtp_packets)
        self.assertIsInstance(rtp_payload, str, "RTP payload should be a string")
        self.assertGreater(len(rtp_payload), 0, "RTP payload should not be empty")

    def test_get_opus_frame_data(self):
        """Test if the get_opus_frame_data function retrieves the correct Opus frame data."""
        opus_frame_data = get_opus_frame_data(self.rtp_packets)
        self.assertIsInstance(opus_frame_data, str, "RTP payload should be a string")
        self.assertGreater(len(opus_frame_data), 0, "RTP payload should not be empty")

    def test_get_rtp_timestamp(self):
        """Test if the get_rtp_timestamp function retrieves the correct RTP timestamp."""
        rtp_timestamp = get_rtp_timestamp(self.rtp_packets)
        self.assertEqual(rtp_timestamp, 2460407020)

    def test_get_via_branches(self):
        """Test if the get_via_branches function retrieves the correct Via branches."""
        via_branches = get_via_branches(self.sip_invite)
        self.assertIsInstance(via_branches, list)
        self.assertGreater(len(via_branches), 0, "Via branches should not be empty")
        self.assertIn("z9hG4bK.EoJ3jqQ1W", via_branches)

    # =========================================================
    #                   Tshark processing Method
    # =========================================================

class TestHandleDuplicates(unittest.TestCase):
    def test_no_duplicates(self):
        """When no keys are duplicated, the result is a simple dict."""
        pairs = [("a", 1), ("b", 2), ("c", 3)]
        result = handle_duplicates(pairs)

        # Ensure the result is a dict
        self.assertIsInstance(result, dict)
        # Ensure the result is not an OrderedDict

        self.assertNotIsInstance(result, OrderedDict)
        self.assertEqual(result, {"a": 1, "b": 2, "c": 3})

    def test_single_duplicate(self):
        """When a key is duplicated, the first value is kept and the second is added to a list."""
        pairs = [("x", 10), ("y", 20), ("x", 30)]
        result = handle_duplicates(pairs)

        # Ensure the result is an OrderedDict
        self.assertIsInstance(result, OrderedDict)

        expected = OrderedDict([
            ("x", [10, 30]),
            ("y", 20),
        ])
        self.assertEqual(result, expected)

    def test_multiple_duplicates_and_order(self):
        """
        When multiple keys are duplicated, the first value is
        kept and subsequent values are added to a list.
        """
        pairs = [
            ("a", 1),
            ("b", 2),
            ("a", 3),
            ("c", 4),
            ("b", 5),
        ]
        result = handle_duplicates(pairs)

        # Ensure the result is an OrderedDict
        self.assertIsInstance(result, OrderedDict)

        expected = OrderedDict([
            ("a", [1, 3]),
            ("b", [2, 5]),
            ("c", 4),
        ])
        self.assertEqual(result, expected)

    def test_empty_list(self):
        """When the input list is empty, the result should be an empty dict."""
        result = handle_duplicates([])
        self.assertEqual(result, {})

    def test_mixed_types(self):
        """When the input contains mixed types, it should handle them correctly."""
        pairs = [("k", "v1"), ("k", "v2"), ("m", None)]
        result = handle_duplicates(pairs)

        # Ensure the result is an OrderedDict
        self.assertIsInstance(result, OrderedDict)

        expected = OrderedDict([
            ("k", ["v1", "v2"]),
            ("m", None),
        ])
        self.assertEqual(result, expected)
