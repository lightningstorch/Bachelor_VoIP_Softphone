import unittest
import json

from datetime import datetime
from unittest.mock import Mock, patch
from queue import Queue, Empty
from data_collection.packet_processor import PacketProcessor
from datastructure.dataclass_models import ParticipantInfo


class TestPacketProcessor(unittest.TestCase):

    def setUp(self):
        self.message_service = Mock()
        self.queue = Queue()
        self.manager_call_context = Mock()
        self.cleanup_queue = Queue()

        self.server_ip_patcher = patch('data_collection.packet_processor.server_ip', '192.168.1.1')
        self.server_ip = self.server_ip_patcher.start()

        self.packet_processor = PacketProcessor(
            message_service=self.message_service,
            queue=self.queue,
            manager_call_context=self.manager_call_context,
            cleanup_queue=self.cleanup_queue
        )


    def tearDown(self):
        # stop all patchers
        self.server_ip_patcher.stop()

    @staticmethod
    def sip_packet():
        mock_sip = Mock()
        mock_sip.method = 'INVITE'
        mock_sip.call_id = '12345'
        mock_sip.from_user = 'user1'
        mock_sip.sdp_media_port = 5060
        mock_sip.sdp_mime_type = 'opus'
        mock_sip.sdp_connection_info_address = '10.0.0.1'

        return mock_sip

    @staticmethod
    def rtp_packet():
        mock_rtp_packet = Mock()
        mock_rtp_packet.ip = Mock()
        mock_rtp_packet.ip.src = "10.0.0.1"
        mock_rtp_packet.ip.dst = "192.168.1.1"  # server_ip
        mock_rtp_packet.udp = Mock()
        mock_rtp_packet.udp.srcport = 5060
        mock_rtp_packet.udp.dstport = 12345

        key = (
            mock_rtp_packet.ip.src,
            mock_rtp_packet.udp.srcport,
            mock_rtp_packet.ip.dst,
            mock_rtp_packet.udp.dstport
        )

        return mock_rtp_packet, key


    def test_run(self):
        """
        Test the run method of the PacketProcessor class.
        Instead of a mock object, class must be used, as a mock object
        returns a new mock for each attribute access by default. This means
        that hasattr(mock_rtp_packet, ‘sip’) returns True, although it should
        be False and the rtp packet is therefore processed incorrectly.
        """

        class SipPacket:
            """Mock SIP packet with a sip attribute"""
            def __init__(self):
                self.sip = object()

        class RtpPacket:
            """Mock RTP packet with a destination IP"""
            def __init__(self, dst_ip):
                self.rtp = object()
                self.ip = type('IP', (), {'dst': dst_ip})()

        sip_packet = SipPacket()
        rtp_packet = RtpPacket(self.server_ip)
        non_server_rtp = RtpPacket("10.0.0.3")  # Not the server IP

        cleanup_id = "test_cleanup_id"

        # Set up method patches
        with patch.object(self.packet_processor, '_clear_call_resources') as mock_clear, \
             patch.object(self.packet_processor, '_sip_process') as mock_sip_process, \
             patch.object(self.packet_processor, '_rtp_process') as mock_rtp_process:

            # Control the number of iterations (5th call returns True to stop loop)
            stop_calls = [False, False, False, False, True]
            self.packet_processor._stop_event.is_set = Mock(side_effect=stop_calls)

            # Set up the queue
            self.packet_processor.queue.get = Mock(side_effect=[sip_packet, rtp_packet, non_server_rtp, Empty()])

            # Set up the cleanup queue
            self.packet_processor.cleanup_queue.get_nowait = Mock(side_effect=[cleanup_id, Empty(), Empty(), Empty()])

            self.packet_processor.run()

            # Verify expected calls
            mock_clear.assert_called_once_with(cleanup_id)
            mock_sip_process.assert_called_once_with(sip_packet)
            mock_rtp_process.assert_called_once_with(rtp_packet)



    def test_sip_process(self):
        """Test the SIP packet processing method for various SIP methods."""
        # Create a base mock packet
        mock_packet = Mock()
        mock_packet.ip = Mock()
        mock_packet.ip.dst = self.server_ip
        mock_packet.ip.src = "10.0.0.1"
        mock_packet.udp = Mock()
        mock_packet.udp.srcport = 5060

        # Create a mock SIP object
        mock_sip = self.sip_packet()

        mock_packet.sip = mock_sip

        with patch.object(self.packet_processor, '_check_dup_packet', return_value=False) as mock_check_dup, \
                patch.object(self.packet_processor, '_sip_incoming_invite') as mock_incoming_invite, \
                patch.object(self.packet_processor, '_sip_incoming_ack') as mock_incoming_ack, \
                patch.object(self.packet_processor, '_sip_incoming_200_invite') as mock_incoming_200_invite, \
                patch.object(self.packet_processor, '_sip_incoming_200_bye') as mock_incoming_200_bye, \
                patch.object(self.packet_processor, '_sip_incoming_603_decline') as mock_incoming_603_decline, \
                patch.object(self.packet_processor, '_outgoing_invite') as mock_outgoing_invite:

            # Test 1: Duplicate packet (should return early)
            with patch.object(self.packet_processor, '_check_dup_packet', return_value=True):
                self.packet_processor._sip_process(mock_packet)
                mock_incoming_invite.assert_not_called()


            # Test 2: Incoming INVITE
            mock_sip.method = 'INVITE'
            mock_sip.request_line = "INVITE sip:user@example.com SIP/2.0"
            delattr(mock_sip, 'status_line') if hasattr(mock_sip, 'status_line') else None

            self.packet_processor._sip_process(mock_packet)
            mock_incoming_invite.assert_called_once_with(mock_sip)
            mock_incoming_invite.reset_mock()

            # Test 3: Incoming ACK
            mock_sip.method = 'ACK'
            self.packet_processor._sip_process(mock_packet)
            mock_incoming_ack.assert_called_once_with(mock_sip, mock_packet)
            mock_incoming_ack.reset_mock()

            # Test 4: Incoming 200 OK for INVITE
            delattr(mock_sip, 'request_line')
            mock_sip.status_line = "SIP/2.0 200 OK"
            mock_sip.status_code = "200"
            mock_sip.cseq_method = "INVITE"

            self.packet_processor._sip_process(mock_packet)
            mock_incoming_200_invite.assert_called_once_with(mock_sip)
            mock_incoming_200_invite.reset_mock()

            # Test 5: Incoming 200 OK for BYE
            mock_sip.status_line = "SIP/2.0 200 OK"
            mock_sip.status_code = "200"
            mock_sip.cseq_method = 'BYE'
            self.packet_processor._sip_process(mock_packet)
            mock_incoming_200_bye.assert_called_once_with(mock_sip, mock_packet)
            mock_incoming_200_bye.reset_mock()

            # Test 6: Incoming 603 Decline
            mock_sip.status_line = "SIP/2.0 603 Decline"
            mock_sip.status_code = "603"
            self.packet_processor._sip_process(mock_packet)
            mock_incoming_603_decline.assert_called_once_with(mock_sip)
            mock_incoming_603_decline.reset_mock()

            # Test 7: Outgoing INVITE
            mock_packet.ip.dst = "10.0.0.2"  # Not server_ip
            mock_sip.request_line = "INVITE sip:user@example.com SIP/2.0"
            mock_sip.method = "INVITE"
            mock_sip.to_user = "user2"
            delattr(mock_sip, 'status_line') if hasattr(mock_sip, 'status_line') else None

            self.packet_processor._sip_process(mock_packet)
            mock_outgoing_invite.assert_called_once_with(mock_sip, mock_sip.to_user)
            mock_outgoing_invite.reset_mock()

            # Test 8: Outgoing INVITE 200 OK
            delattr(mock_sip, 'request_line')
            mock_sip.status_line = "SIP/2.0 200 OK"
            mock_sip.status_code = "200"
            mock_sip.cseq_method = "INVITE"
            mock_sip.from_user = "user1"

            self.packet_processor._sip_process(mock_packet)
            mock_outgoing_invite.assert_called_once_with(mock_sip, mock_sip.from_user)

    def test_rtp_process_no_mapping(self):
        """Test that the RTP packet is buffered when there is no mapping."""
        mock_rtp_packet, key = self.rtp_packet()

        with patch.object(self.packet_processor, '_handle_rtp_packet') as mock_handle_rtp_packet:
            self.packet_processor._rtp_process(mock_rtp_packet)

            # Check that the rtp handle was not called
            mock_handle_rtp_packet.assert_not_called()

            # Check that the call_map is updated correctly
            self.assertIn(key, self.packet_processor._rtp_buffer)
            self.assertEqual(len(self.packet_processor._rtp_buffer), 1)
            self.assertEqual(self.packet_processor._rtp_buffer[key][0], mock_rtp_packet)

    def test_rtp_process_with_mapping(self):
        """Test that the RTP packet is processed correctly when there is a mapping."""
        mock_rtp_packet, key = self.rtp_packet()

        buffered_packet = Mock()
        self.packet_processor._rtp_buffer[key] = [buffered_packet]

        call_id = "test_call_id"
        user = "test_user"
        self.packet_processor._call_map[key] = (call_id, user)

        with patch.object(self.packet_processor, '_handle_rtp_packet') as mock_handle_rtp_packet:
            self.packet_processor._rtp_process(mock_rtp_packet)

            self.assertEqual(mock_handle_rtp_packet.call_count, 2)

            # first the buffered packet should be removed from the buffer
            mock_handle_rtp_packet.assert_any_call(buffered_packet, call_id, user)

            # second the new packet should be added to the buffer
            mock_handle_rtp_packet.assert_any_call(mock_rtp_packet, call_id, user)

            self.assertNotIn(key, self.packet_processor._rtp_buffer)

    @patch('data_collection.packet_processor.ExchangeType')
    def test_sip_incoming_invite(self, mock_exchange_type):
        """Test that the incoming SIP INVITE is processed correctly."""
        mock_sip = self.sip_packet()

        self.packet_processor._sip_incoming_invite(mock_sip)

        self.check_data_in_buffer(mock_sip)

        self.assertEqual(self.message_service.publish.call_count, 2)

        first_message = self.message_service.publish.call_args_list[0]
        first_args = json.loads(first_message.args[0])
        first_kwargs = first_message.kwargs


        self.assertEqual(first_kwargs['exchange_name'], "NEW_CALL")
        self.assertEqual(first_kwargs['exchange_type'], mock_exchange_type.DIRECT)
        self.assertEqual(first_kwargs['routing_key'], "new_call")

        self.assertEqual(first_args["call_id"], mock_sip.call_id)
        self.assertEqual(first_args["caller"], mock_sip.from_user)

        # check the participant message in a separate function
        message = self.message_service.publish.call_args_list[1]
        self.check_participant_message(message, mock_sip)

    def test_sip_incoming_200_invite(self):
        """Test that the incoming SIP 200 OK is processed correctly."""
        mock_sip = self.sip_packet()
        mock_sip.method = 'INVITE'
        mock_sip.status_code = '200 OK'
        mock_sip.sdp_sample_rate = 48000
        mock_sip.to_user = 'to_user'

        with (patch.object(self.packet_processor, '_publish_and_store_participant')
              as mock_publish_and_store_participant):


            self.packet_processor._sip_incoming_200_invite(mock_sip)

            self.manager_call_context.create_or_insert_call_context.assert_called_once_with(
                call_id=mock_sip.call_id,
                sample_rate=int(mock_sip.sdp_sample_rate)
            )

            mock_publish_and_store_participant.assert_called_once_with(mock_sip, mock_sip.to_user)

    def test_sip_incoming_ack(self):
        """Test that the incoming SIP ACK is processed correctly."""
        mock_sip = self.sip_packet()
        mock_sip.method = 'ACK'

        mock_packet = Mock()
        mock_packet.sip = mock_sip
        mock_packet.sniff_time = datetime.now()

        self.packet_processor._sip_incoming_ack(mock_sip, mock_packet)

        self.assertEqual(self.message_service.publish.call_count, 1)

        message = self.message_service.publish.call_args_list[0]
        args = json.loads(message.args[0])
        kwargs = message.kwargs

        self.assertEqual(kwargs['exchange_name'], "ACK")
        self.assertEqual(kwargs['routing_key'], "ack")

        self.assertEqual(args["call_id"], mock_sip.call_id)
        self.assertEqual(args["start_time"], mock_packet.sniff_time.isoformat())

    def test_sip_incoming_200_bye(self):

        mock_sip = self.sip_packet()
        mock_sip.method = 'BYE'

        mock_packet = Mock()
        mock_packet.sip = mock_sip
        mock_packet.sniff_time = datetime.now()

        self.packet_processor._sip_incoming_200_bye(mock_sip, mock_packet)

        self.assertEqual(self.message_service.publish.call_count, 1)

        message = self.message_service.publish.call_args_list[0]
        args = json.loads(message.args[0])
        kwargs = message.kwargs

        self.assertEqual(kwargs['exchange_name'], "CALL_END")
        self.assertEqual(kwargs['routing_key'], "end_call")

        self.assertEqual(args["call_id"], mock_sip.call_id)
        self.assertEqual(args["end_time"], mock_packet.sniff_time.isoformat())

    def test_sip_incoming_603_decline(self):
        mock_sip = self.sip_packet()
        mock_sip.status_code = '603'

        mock_packet = Mock()
        mock_packet.sip = mock_sip
        mock_packet.sniff_time = datetime.now()

        self.packet_processor._sip_incoming_603_decline(mock_sip)

        self.assertEqual(self.message_service.publish.call_count, 1)

        message = self.message_service.publish.call_args_list[0]
        args = json.loads(message.args[0])
        kwargs = message.kwargs

        self.assertEqual(kwargs['exchange_name'], "CALL_DECLINE")
        self.assertEqual(kwargs['routing_key'], "call_decline")

        self.assertEqual(args["call_id"], mock_sip.call_id)

    def test_outgoing_invite(self):
        """Test that the outgoing SIP INVITE is processed correctly."""
        mock_sip = self.sip_packet()
        mock_sip.method = 'INVITE'
        mock_sip.sdp_connection_info_address = self.server_ip
        mock_sip.sdp_media_port = 12345

        fields = {
            "user": mock_sip.from_user,
            "server_ip": mock_sip.sdp_connection_info_address,
            "server_port": mock_sip.sdp_media_port
        }

        with patch.object(self.packet_processor, '_store_in_buffer') as mock_store_in_buffer:

            self.packet_processor._outgoing_invite(mock_sip, mock_sip.from_user)
            mock_store_in_buffer.assert_called_once_with(mock_sip.call_id, **fields)

    def test_handle_rtp_packet_existing_ssrc(self):
        mock_rtp_packet = Mock()
        mock_rtp = Mock()
        mock_rtp_packet.rtp = mock_rtp
        mock_rtp.ssrc = "0x123456789"

        call_id = "test_call_id"
        user = "user1"

        self.packet_processor._ssrc_to_call_id[mock_rtp.ssrc] = (call_id, user)

        self.packet_processor._handle_rtp_packet(mock_rtp_packet, call_id, user)

        ssrc_to_call_id = self.packet_processor._ssrc_to_call_id[mock_rtp.ssrc]
        self.assertIn(call_id, ssrc_to_call_id)
        self.assertIn(user, ssrc_to_call_id)

        self.manager_call_context.enqueue_packet.assert_called_with(call_id, mock_rtp.ssrc, mock_rtp_packet)

    def test_handle_rtp_packet_not_existing_ssrc(self):
        mock_rtp_packet = Mock()
        mock_rtp = Mock()
        mock_rtp_packet.rtp = mock_rtp
        mock_rtp.ssrc = "0x123456789"

        call_id = "test_call_id"
        user = "user1"

        self.packet_processor._handle_rtp_packet(mock_rtp_packet, call_id, user)

        ssrc_to_call_id = self.packet_processor._ssrc_to_call_id[mock_rtp.ssrc]
        self.assertEqual(call_id, ssrc_to_call_id[0])
        self.assertEqual(user, ssrc_to_call_id[1])

        self.message_service.publish.assert_called_once()
        message = self.message_service.publish.call_args_list[0]
        args = json.loads(message.args[0])
        kwargs = message.kwargs

        self.assertEqual(kwargs['exchange_name'], "SSRC")
        self.assertEqual(kwargs['routing_key'], "ssrc")

        self.assertEqual(args["call_id"], call_id)
        self.assertEqual(args["user"], user)
        self.assertEqual(args["ssrc"], mock_rtp.ssrc)

    def test_send_server_info(self):
        """Test that the server info is sent correctly."""
        # Mock the SIP packet with server infos (server IP and port)
        mock_sip = self.sip_packet()
        mock_sip.sdp_connection_info_address = self.server_ip
        mock_sip.sdp_media_port = 12345

        self.packet_processor._send_server_info(mock_sip, mock_sip.from_user)

        self.assertEqual(self.message_service.publish.call_count, 1)

        message = self.message_service.publish.call_args_list[0]
        second_args = json.loads(message.args[0])
        second_kwargs = message.kwargs

        self.assertEqual(second_kwargs['exchange_name'], "SERVER_INFO")
        self.assertEqual(second_kwargs['routing_key'], "server_info")

        self.assertEqual(second_args["call_id"], mock_sip.call_id)
        self.assertEqual(second_args["server_ip"], self.server_ip)
        self.assertEqual(second_args["server_port"], mock_sip.sdp_media_port)
        self.assertEqual(second_args["user"], mock_sip.from_user)

    @patch('data_collection.packet_processor.ExchangeType')
    def test_publish_and_store_participant(self, mock_exchange_type):
        """Test that the participant is published and stored correctly."""
        mock_sip = self.sip_packet()

        self.packet_processor._publish_and_store_participant(
            sip= mock_sip,
            user=mock_sip.from_user,
        )

        self.check_data_in_buffer(mock_sip)

        self.assertEqual(self.message_service.publish.call_count, 1)

        # check the participant message in a separate function
        message = self.message_service.publish.call_args_list[0]
        self.check_participant_message(message, mock_sip)

    def test_store_in_buffer(self):
        """Test that the data is stored in the buffer correctly."""
        mock_sip = self.sip_packet()

        fields = {
            "user": mock_sip.from_user,
            "ip_address": mock_sip.sdp_connection_info_address,
            "media_port": mock_sip.sdp_media_port,
            "mime_type": mock_sip.sdp_mime_type,
        }

        self.packet_processor._store_in_buffer(
            call_id=mock_sip.call_id,
            **fields,
        )

        self.check_data_in_buffer(mock_sip)

        # Check that the call_id is in the buffer
        self.assertIn(mock_sip.call_id, self.packet_processor._ip_port_buffer)

        # Check that the user is stored correctly
        participant_info = self.packet_processor._ip_port_buffer[mock_sip.call_id][0]
        self.assertEqual(participant_info.user, mock_sip.from_user)
        self.assertEqual(participant_info.ip_address, mock_sip.sdp_connection_info_address)
        self.assertEqual(participant_info.media_port, mock_sip.sdp_media_port)
        self.assertEqual(participant_info.mime_type, mock_sip.sdp_mime_type)

    def test_clear_call_resources(self):
        """Test that the call resources are cleared correctly."""
        mock_sip = self.sip_packet()
        server_port = 12345
        ssrc = "0x123456789"

        # insert in the _ip_port_buffer
        self.packet_processor._ip_port_buffer[mock_sip.call_id] = [
            ParticipantInfo(
                user=mock_sip.from_user,
                ip_address=mock_sip.sdp_connection_info_address,
                media_port=mock_sip.sdp_media_port,
                server_ip=self.server_ip,
                server_port=server_port,
            )
        ]

        # insert in _call_mal buffer
        key = (mock_sip.sdp_connection_info_address, mock_sip.sdp_media_port, self.server_ip, server_port)
        self.packet_processor._call_map[key] = (mock_sip.call_id, mock_sip.from_user)

        # insert in _ssrc_to_call_id mapping
        self.packet_processor._ssrc_to_call_id[ssrc] = (mock_sip.call_id, mock_sip.from_user)


        # Call the method to clear resources
        self.packet_processor._clear_call_resources(mock_sip.call_id)

        # Check that the call ID is removed from the buffer
        self.assertNotIn(mock_sip.call_id, self.packet_processor._ip_port_buffer)
        self.assertNotIn(key, self.packet_processor._call_map)
        self.assertNotIn(ssrc, self.packet_processor._ssrc_to_call_id)

    def test_store_buffer_in_call_map(self):
        """Test that the call map is updated correctly when storing in buffer."""
        mock_sip = self.sip_packet()
        server_port = 12345

        self.packet_processor._ip_port_buffer[mock_sip.call_id] = []

        participant_info = ParticipantInfo(
            user=mock_sip.from_user,
            server_ip=self.server_ip,
            server_port=server_port,
        )
        self.packet_processor._ip_port_buffer[mock_sip.call_id].append(participant_info)

        fields = {
            "user": mock_sip.from_user,
            "ip_address": mock_sip.sdp_connection_info_address,
            "media_port": mock_sip.sdp_media_port,
            "mime_type": mock_sip.sdp_mime_type,
        }

        with patch.object(self.packet_processor, '_call_ready', return_value=True):
            self.packet_processor._store_in_buffer(
                call_id=mock_sip.call_id,
                **fields,
            )

        key = (mock_sip.sdp_connection_info_address, mock_sip.sdp_media_port, self.server_ip, server_port)
        call_map_data = self.packet_processor._call_map.get(key)

        self.assertEqual(call_map_data[0], mock_sip.call_id)
        self.assertEqual(call_map_data[1], participant_info.user)

    def test_call_ready(self):
        """Test that the call is ready when there are two participants in the buffer."""
        mock_sip = self.sip_packet()

        # Simulate that the call is ready
        self.packet_processor._ip_port_buffer[mock_sip.call_id].append(
            ParticipantInfo(
                user=mock_sip.from_user,
                ip_address=mock_sip.sdp_connection_info_address,
                media_port=mock_sip.sdp_media_port,
                server_ip=self.server_ip,
                server_port=54321,
            )
        )

        self.packet_processor._ip_port_buffer[mock_sip.call_id].append(
            ParticipantInfo(
                user="from_user",
                ip_address="10.0.0.0",
                media_port=123456,
                server_ip=self.server_ip,
                server_port=98765,
            )
        )

        result = self.packet_processor._call_ready(mock_sip.call_id)

        self.assertTrue(result)

    def test_check_dup_packet(self):
        """Test that duplicate packets are detected correctly."""

        # Create mock SIP object with necessary attributes
        mock_sip = Mock()
        mock_sip.call_id = "12345"
        mock_sip.via_branch = "z9hG4bK-12345"
        mock_sip.method = "INVITE"
        mock_sip.status_code = None

        # Create mock packet with necessary attributes
        mock_packet = Mock()
        mock_packet.sip = mock_sip
        mock_packet.ip = Mock()
        mock_packet.ip.src = "10.0.0.1"
        mock_packet.udp = Mock()
        mock_packet.udp.srcport = 5060

        # Check the first packet if it is considered duplicate
        result1 = self.packet_processor._check_dup_packet(mock_sip, mock_packet)
        self.assertFalse(result1, "Packet should not be considered duplicate on first check")

        # Check the same packet with identical attributes if it is considered duplicate
        result2 = self.packet_processor._check_dup_packet(mock_sip, mock_packet)
        self.assertTrue(result2, "Same packet should be considered duplicate on second check")

        # Create a new mock packet with different attributes
        mock_sip2 = Mock()
        mock_sip2.sip = mock_sip
        mock_sip2.call_id = "12345"
        mock_sip2.via_branch = "z9hG4bK-12345"
        mock_sip2.method = None
        mock_sip2.status_code = "200"  # Different attribute

        # Create a new mock packet with the same call_id but different attributes
        result3 = self.packet_processor._check_dup_packet(mock_sip2, mock_packet)
        self.assertFalse(result3, "Different packet should not be considered duplicate")

        # Check the same packet with identical attributes if it is considered duplicate
        result4 = self.packet_processor._check_dup_packet(mock_sip2, mock_packet)
        self.assertTrue(result4, "Same packet with different attributes should be considered duplicate")

    #=====================================================
    #   Helper methods for checking data and messages
    #=====================================================

    def check_data_in_buffer(self, mock_sip):
        """Check that the data is stored in the buffer correctly."""
        self.assertIn(mock_sip.call_id, self.packet_processor._ip_port_buffer)
        participant_info = self.packet_processor._ip_port_buffer[mock_sip.call_id][0]
        self.assertEqual(participant_info.user, mock_sip.from_user)

    def check_participant_message(self, message, mock_sip):
        """Check that the participant message is published correctly."""
        second_args = json.loads(message.args[0])
        second_kwargs = message.kwargs

        self.assertEqual(second_kwargs['exchange_name'], "PARTICIPANTS")
        self.assertEqual(second_kwargs['routing_key'], "participation")

        self.assertEqual(second_args["call_id"], mock_sip.call_id)
        self.assertEqual(second_args["user"], mock_sip.from_user)
        self.assertEqual(second_args["ip_address"], mock_sip.sdp_connection_info_address)
        self.assertEqual(second_args["media_port"], mock_sip.sdp_media_port)
        self.assertEqual(second_args["mime_type"], mock_sip.sdp_mime_type)




















