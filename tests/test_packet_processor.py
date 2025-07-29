import unittest
import json

from unittest.mock import Mock, patch
from queue import Queue, Empty
from data_collection.packet_processor import PacketProcessor
from datastructure.dataclass_models import ParticipantInfo
from utils.packet_parsing import get_layer, get_ip_src, get_ip_dst, get_udp_srcport, get_udp_dstport, \
    get_to_user, get_from_user, get_call_id, get_media_port, get_preferred_codec_sample_rate, \
    get_sdp_connection_info_address, get_time_stamp_isoformat, get_ssrc
from tests.utils_tests.load_file import get_rtp_sample_data, get_sip_sample_data


class TestPacketProcessor(unittest.TestCase):

    def setUp(self):
        self.message_service = Mock()
        self.queue = Queue()
        self.manager_call_context = Mock()
        self.cleanup_queue = Queue()

        self.server_ip_patcher = patch('data_collection.packet_processor.server_ip', '192.168.0.63')
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

    def test_run(self):
        """
        Test the run method of the PacketProcessor class.
        Instead of a mock object, class must be used, as a mock object
        returns a new mock for each attribute access by default. This means
        that hasattr(mock_rtp_packet, ‘sip’) returns True, although it should
        be False and the rtp packet is therefore processed incorrectly.
        """
        cleanup_id = "test_cleanup_id"

        sip_packet = get_sip_sample_data("invite_incoming")
        rtp_packet = get_rtp_sample_data()

        sip_layer = get_layer(sip_packet, 'sip')
        non_server_rtp = {"_source": {"layers": {"ip": {"ip.dst": "10.0.0.3"}}}}

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
            mock_sip_process.assert_called_once_with(sip_packet, sip_layer)
            mock_rtp_process.assert_called_once_with(rtp_packet)

    def test_sip_process(self):
        """Test the SIP packet processing method for various SIP methods."""
        # Create a base mock packet
        sip_packet = get_sip_sample_data("invite_incoming")
        sip_layer = get_layer(sip_packet, 'sip')

        with patch.object(self.packet_processor, '_check_dup_packet', return_value=False) as mock_check_dup, \
                patch.object(self.packet_processor, '_sip_incoming_invite') as mock_incoming_invite, \
                patch.object(self.packet_processor, '_sip_incoming_ack') as mock_incoming_ack, \
                patch.object(self.packet_processor, '_sip_incoming_200_invite') as mock_incoming_200_invite, \
                patch.object(self.packet_processor, '_sip_incoming_200_bye') as mock_incoming_200_bye, \
                patch.object(self.packet_processor, '_sip_incoming_603_decline') as mock_incoming_603_decline, \
                patch.object(self.packet_processor, '_outgoing_invite') as mock_outgoing_invite:

            # Test 1: Duplicate packet (should return early)
            with patch.object(self.packet_processor, '_check_dup_packet', return_value=True):
                self.packet_processor._sip_process(sip_packet, sip_layer)
                mock_incoming_invite.assert_not_called()


            # Test 2: Incoming INVITE
            self.packet_processor._sip_process(sip_packet, sip_layer)
            mock_incoming_invite.assert_called_once_with(sip_layer)
            mock_incoming_invite.reset_mock()

            # Test 3: Incoming ACK
            sip_packet = get_sip_sample_data("ack")
            sip_layer = get_layer(sip_packet, 'sip')
            self.packet_processor._sip_process(sip_packet, sip_layer)
            mock_incoming_ack.assert_called_once_with(sip_layer, sip_packet)
            mock_incoming_ack.reset_mock()

            # Test 4: Incoming 200 OK for INVITE
            sip_packet = get_sip_sample_data("200_invite_incoming")
            sip_layer = get_layer(sip_packet, 'sip')
            self.packet_processor._sip_process(sip_packet, sip_layer)
            mock_incoming_200_invite.assert_called_once_with(sip_layer)
            mock_incoming_200_invite.reset_mock()

            # Test 5: Incoming 200 OK for BYE
            sip_packet = get_sip_sample_data("200_bye")
            sip_layer = get_layer(sip_packet, 'sip')
            self.packet_processor._sip_process(sip_packet, sip_layer)
            mock_incoming_200_bye.assert_called_once_with(sip_layer, sip_packet)
            mock_incoming_200_bye.reset_mock()

            # Test 6: Incoming 603 Decline
            sip_packet = get_sip_sample_data("603_decline")
            sip_layer = get_layer(sip_packet, 'sip')
            self.packet_processor._sip_process(sip_packet, sip_layer)
            mock_incoming_603_decline.assert_called_once_with(sip_layer)
            mock_incoming_603_decline.reset_mock()

            # Test 7: Outgoing INVITE
            sip_packet = get_sip_sample_data("invite_outgoing")
            sip_layer = get_layer(sip_packet, 'sip')
            self.packet_processor._sip_process(sip_packet, sip_layer)
            mock_outgoing_invite.assert_called_once_with(sip_layer, get_to_user(sip_layer))
            mock_outgoing_invite.reset_mock()

            # Test 8: Outgoing INVITE 200 OK
            sip_packet = get_sip_sample_data("200_invite_outgoing")
            sip_layer = get_layer(sip_packet, 'sip')
            self.packet_processor._sip_process(sip_packet, sip_layer)
            mock_outgoing_invite.assert_called_once_with(sip_layer, get_from_user(sip_layer))


    def test_rtp_process_no_mapping(self):
        """Test that the RTP packet is buffered when there is no mapping."""
        rtp_packet = get_rtp_sample_data()

        ip_src = get_ip_src(rtp_packet)
        udp_srcport = get_udp_srcport(rtp_packet)
        ip_dst = get_ip_dst(rtp_packet)
        udp_dstport = get_udp_dstport(rtp_packet)

        key = (ip_src, udp_srcport, ip_dst, udp_dstport)

        with patch.object(self.packet_processor, '_handle_rtp_packet') as mock_handle_rtp_packet:
            self.packet_processor._rtp_process(rtp_packet)

            # Check that the rtp handle was not called
            mock_handle_rtp_packet.assert_not_called()

            # Check that the call_map is updated correctly
            self.assertIn(key, self.packet_processor._rtp_buffer)
            self.assertEqual(len(self.packet_processor._rtp_buffer), 1)
            self.assertEqual(self.packet_processor._rtp_buffer[key][0], rtp_packet)

    def test_rtp_process_with_mapping(self):
        """Test that the RTP packet is processed correctly when there is a mapping."""
        rtp_packet = get_rtp_sample_data()

        ip_src = get_ip_src(rtp_packet)
        udp_srcport = get_udp_srcport(rtp_packet)
        ip_dst = get_ip_dst(rtp_packet)
        udp_dstport = get_udp_dstport(rtp_packet)

        key = (ip_src, udp_srcport, ip_dst, udp_dstport)

        buffered_packet = Mock()
        self.packet_processor._rtp_buffer[key] = [buffered_packet]

        call_id = "test_call_id"
        user = "test_user"
        self.packet_processor._call_map[key] = (call_id, user)

        with patch.object(self.packet_processor, '_handle_rtp_packet') as mock_handle_rtp_packet:
            self.packet_processor._rtp_process(rtp_packet)

            self.assertEqual(mock_handle_rtp_packet.call_count, 2)

            # first the buffered packet should be removed from the buffer
            mock_handle_rtp_packet.assert_any_call(buffered_packet, call_id, user)

            # second the new packet should be added to the buffer
            mock_handle_rtp_packet.assert_any_call(rtp_packet, call_id, user)

            self.assertNotIn(key, self.packet_processor._rtp_buffer)

    @patch('data_collection.packet_processor.ExchangeType')
    def test_sip_incoming_invite(self, mock_exchange_type):
        """Test that the incoming SIP INVITE is processed correctly."""
        sip_packet = get_sip_sample_data("invite_incoming")
        sip_layer = get_layer(sip_packet, 'sip')
        call_id = get_call_id(sip_layer)
        from_user = get_from_user(sip_layer)

        self.packet_processor._sip_incoming_invite(sip_layer)

        self.check_data_in_buffer(sip_layer)

        self.assertEqual(self.message_service.publish.call_count, 2)

        first_message = self.message_service.publish.call_args_list[0]
        first_args = json.loads(first_message.args[0])
        first_kwargs = first_message.kwargs


        self.assertEqual(first_kwargs['exchange_name'], "NEW_CALL")
        self.assertEqual(first_kwargs['exchange_type'], mock_exchange_type.DIRECT)
        self.assertEqual(first_kwargs['routing_key'], "new_call")

        self.assertEqual(first_args["call_id"], call_id)
        self.assertEqual(first_args["caller"], from_user)

        # check the participant message in a separate function
        message = self.message_service.publish.call_args_list[1]
        self.check_participant_message(message, sip_layer)

    def test_sip_incoming_200_invite(self):
        """Test that the incoming SIP 200 OK is processed correctly."""
        sip_packet = get_sip_sample_data("200_invite_incoming")
        sip_layer = get_layer(sip_packet, 'sip')

        call_id = get_call_id(sip_layer)
        to_user = get_to_user(sip_layer)
        mime_type, sample_rate = get_preferred_codec_sample_rate(sip_layer)

        with (patch.object(self.packet_processor, '_publish_and_store_participant')
              as mock_publish_and_store_participant):


            self.packet_processor._sip_incoming_200_invite(sip_layer)

            self.manager_call_context.create_or_insert_call_context.assert_called_once_with(
                call_id=call_id,
                sample_rate=int(sample_rate)
            )

            mock_publish_and_store_participant.assert_called_once_with(sip_layer, to_user)

    def test_sip_incoming_ack(self):
        """Test that the incoming SIP ACK is processed correctly."""
        sip_packet = get_sip_sample_data("ack")
        sip_layer = get_layer(sip_packet, 'sip')

        call_id = get_call_id(sip_layer)
        time_stamp = get_time_stamp_isoformat(sip_packet)

        self.packet_processor._sip_incoming_ack(sip_layer, sip_packet)

        self.assertEqual(self.message_service.publish.call_count, 1)

        message = self.message_service.publish.call_args_list[0]
        args = json.loads(message.args[0])
        kwargs = message.kwargs

        self.assertEqual(kwargs['exchange_name'], "ACK")
        self.assertEqual(kwargs['routing_key'], "ack")

        self.assertEqual(args["call_id"], call_id)
        self.assertEqual(args["start_time"], time_stamp)

    def test_sip_incoming_200_bye(self):
        sip_packet = get_sip_sample_data("200_bye")
        sip_layer = get_layer(sip_packet, 'sip')

        call_id = get_call_id(sip_layer)
        time_stamp = get_time_stamp_isoformat(sip_packet)

        self.packet_processor._sip_incoming_200_bye(sip_layer, sip_packet)

        self.assertEqual(self.message_service.publish.call_count, 1)

        message = self.message_service.publish.call_args_list[0]
        args = json.loads(message.args[0])
        kwargs = message.kwargs

        self.assertEqual(kwargs['exchange_name'], "CALL_END")
        self.assertEqual(kwargs['routing_key'], "end_call")

        self.assertEqual(args["call_id"], call_id)
        self.assertEqual(args["end_time"], time_stamp)

    def test_sip_incoming_603_decline(self):
        sip_packet = get_sip_sample_data("603_decline")
        sip_layer = get_layer(sip_packet, 'sip')

        call_id = get_call_id(sip_layer)


        self.packet_processor._sip_incoming_603_decline(sip_layer)

        self.assertEqual(self.message_service.publish.call_count, 1)

        message = self.message_service.publish.call_args_list[0]
        args = json.loads(message.args[0])
        kwargs = message.kwargs

        self.assertEqual(kwargs['exchange_name'], "CALL_DECLINE")
        self.assertEqual(kwargs['routing_key'], "call_decline")

        self.assertEqual(args["call_id"], call_id)

    def test_outgoing_invite(self):
        """Test that the outgoing SIP INVITE is processed correctly."""
        sip_packet = get_sip_sample_data("invite_outgoing")
        sip_layer = get_layer(sip_packet, 'sip')

        call_id = get_call_id(sip_layer)
        sdp_connection_info_address = get_sdp_connection_info_address(sip_layer)
        media_port = get_media_port(sip_layer)
        from_user = get_from_user(sip_layer)

        fields = {
            "user": from_user,
            "server_ip": sdp_connection_info_address,
            "server_port": media_port
        }

        with patch.object(self.packet_processor, '_store_in_buffer') as mock_store_in_buffer:

            self.packet_processor._outgoing_invite(sip_layer, from_user)
            mock_store_in_buffer.assert_called_once_with(call_id, **fields)

    def test_send_server_info(self):
        """Test that the server info is sent correctly."""
        # Mock the SIP packet with server infos (server IP and port)
        sip_packet = get_sip_sample_data("invite_outgoing")
        sip_layer = get_layer(sip_packet, 'sip')

        call_id = get_call_id(sip_layer)
        media_port = int(get_media_port(sip_layer))
        from_user = get_from_user(sip_layer)

        self.packet_processor._send_server_info(sip_layer, from_user)

        self.assertEqual(self.message_service.publish.call_count, 1)

        message = self.message_service.publish.call_args_list[0]
        second_args = json.loads(message.args[0])
        second_kwargs = message.kwargs

        self.assertEqual(second_kwargs['exchange_name'], "SERVER_INFO")
        self.assertEqual(second_kwargs['routing_key'], "server_info")

        self.assertEqual(second_args["call_id"], call_id)
        self.assertEqual(second_args["server_ip"], self.server_ip)
        self.assertEqual(second_args["server_port"], media_port)
        self.assertEqual(second_args["user"], from_user)

    def test_handle_rtp_packet_existing_ssrc(self):
        """Test that the RTP packet is handled correctly when the SSRC already exists."""
        rtp_packet = get_rtp_sample_data()
        ssrc = get_ssrc(rtp_packet)

        call_id = get_call_id(rtp_packet)
        user = get_from_user(rtp_packet)

        self.packet_processor._ssrc_to_call_id[ssrc] = (call_id, user)

        self.packet_processor._handle_rtp_packet(rtp_packet, call_id, user)

        ssrc_to_call_id = self.packet_processor._ssrc_to_call_id[ssrc]
        self.assertIn(call_id, ssrc_to_call_id)
        self.assertIn(user, ssrc_to_call_id)

        self.manager_call_context.enqueue_packet.assert_called_with(call_id, ssrc, rtp_packet)

    def test_handle_rtp_packet_not_existing_ssrc(self):
        """Test that the RTP packet is buffered when the SSRC does not exist."""
        rtp_packet = get_rtp_sample_data()
        ssrc = get_ssrc(rtp_packet)

        call_id = get_call_id(rtp_packet)
        user = get_from_user(rtp_packet)

        self.packet_processor._handle_rtp_packet(rtp_packet, call_id, user)

        ssrc_to_call_id = self.packet_processor._ssrc_to_call_id[ssrc]
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
        self.assertEqual(args["ssrc"], ssrc)

    @patch('data_collection.packet_processor.ExchangeType')
    def test_publish_and_store_participant(self, mock_exchange_type):
        """Test that the participant is published and stored correctly."""
        sip_packet = get_sip_sample_data("invite_incoming")
        sip_layer = get_layer(sip_packet, 'sip')
        from_user = get_from_user(sip_layer)


        self.packet_processor._publish_and_store_participant(
            sip= sip_layer,
            user=from_user,
        )

        self.check_data_in_buffer(sip_layer)

        self.assertEqual(self.message_service.publish.call_count, 1)

        # check the participant message in a separate function
        message = self.message_service.publish.call_args_list[0]
        self.check_participant_message(message, sip_layer)

    def test_store_in_buffer(self):
        """Test that the data is stored in the buffer correctly."""
        sip_packet = get_sip_sample_data("invite_incoming")
        sip_layer = get_layer(sip_packet, 'sip')

        call_id = get_call_id(sip_layer)
        from_user = get_from_user(sip_layer)
        sdp_connection_info_address = get_sdp_connection_info_address(sip_layer)
        media_port = get_media_port(sip_layer)

        mime_type, _ = get_preferred_codec_sample_rate(sip_layer)

        fields = {
            "user": from_user,
            "ip_address": sdp_connection_info_address,
            "media_port": media_port,
            "mime_type": mime_type,
        }

        self.packet_processor._store_in_buffer(
            call_id=call_id,
            **fields,
        )

        self.check_data_in_buffer(sip_layer)

        # Check that the call_id is in the buffer
        self.assertIn(call_id, self.packet_processor._ip_port_buffer)

        # Check that the user is stored correctly
        participant_info = self.packet_processor._ip_port_buffer[call_id][0]
        self.assertEqual(participant_info.user, from_user)
        self.assertEqual(participant_info.ip_address, sdp_connection_info_address)
        self.assertEqual(participant_info.media_port, media_port)
        self.assertEqual(participant_info.mime_type, mime_type)

    def test_clear_call_resources(self):
        """Test that the call resources are cleared correctly."""
        sip_packet = get_sip_sample_data("invite_incoming")
        sip_layer = get_layer(sip_packet, 'sip')

        call_id = get_call_id(sip_layer)
        from_user = get_from_user(sip_layer)
        sdp_connection_info_address = get_sdp_connection_info_address(sip_layer)
        media_port = get_media_port(sip_layer)
        server_port = get_udp_dstport(sip_packet)

        rtp_packet = get_rtp_sample_data()
        ssrc = get_ssrc(rtp_packet)

        # insert in the _ip_port_buffer
        self.packet_processor._ip_port_buffer[call_id] = [
            ParticipantInfo(
                user=from_user,
                ip_address=sdp_connection_info_address,
                media_port=media_port,
                server_ip=self.server_ip,
                server_port=server_port,
            )
        ]

        # insert in _call_mal buffer
        key = (sdp_connection_info_address, media_port, self.server_ip, server_port)
        self.packet_processor._call_map[key] = (call_id, from_user)

        # insert in _ssrc_to_call_id mapping
        self.packet_processor._ssrc_to_call_id[ssrc] = (call_id, from_user)


        # Call the method to clear resources
        self.packet_processor._clear_call_resources(call_id)

        # Check that the call ID is removed from the buffer
        self.assertNotIn(call_id, self.packet_processor._ip_port_buffer)
        self.assertNotIn(key, self.packet_processor._call_map)
        self.assertNotIn(ssrc, self.packet_processor._ssrc_to_call_id)

    def test_store_buffer_in_call_map(self):
        """Test that the call map is updated correctly when storing in buffer."""
        sip_packet = get_sip_sample_data("invite_incoming")
        sip_layer = get_layer(sip_packet, 'sip')

        call_id = get_call_id(sip_layer)
        from_user = get_from_user(sip_layer)
        sdp_connection_info_address = get_sdp_connection_info_address(sip_layer)
        media_port = get_media_port(sip_layer)
        server_port = get_udp_dstport(sip_packet)
        mime_type, _ = get_preferred_codec_sample_rate(sip_layer)

        self.packet_processor._ip_port_buffer[call_id] = []

        participant_info = ParticipantInfo(
            user=from_user,
            server_ip=self.server_ip,
            server_port=server_port,
        )
        self.packet_processor._ip_port_buffer[call_id].append(participant_info)

        fields = {
            "user": from_user,
            "ip_address": sdp_connection_info_address,
            "media_port": media_port,
            "mime_type": mime_type,
        }

        with patch.object(self.packet_processor, '_call_ready', return_value=True):
            self.packet_processor._store_in_buffer(
                call_id=call_id,
                **fields,
            )

        key = (sdp_connection_info_address, media_port, self.server_ip, server_port)
        call_map_data = self.packet_processor._call_map.get(key)

        self.assertEqual(call_map_data[0], call_id)
        self.assertEqual(call_map_data[1], participant_info.user)

    def test_call_ready(self):
        """Test that the call is ready when there are two participants in the buffer."""
        sip_packet = get_sip_sample_data("invite_incoming")
        sip_layer = get_layer(sip_packet, 'sip')

        call_id = get_call_id(sip_layer)
        from_user = get_from_user(sip_layer)
        sdp_connection_info_address = get_sdp_connection_info_address(sip_layer)
        media_port = get_media_port(sip_layer)
        server_port = get_udp_dstport(sip_packet)
        mime_type, _ = get_preferred_codec_sample_rate(sip_layer)



        # Simulate that the call is ready
        self.packet_processor._ip_port_buffer[call_id].append(
            ParticipantInfo(
                user=from_user,
                ip_address=sdp_connection_info_address,
                media_port=media_port,
                server_ip=self.server_ip,
                server_port=server_port,
            )
        )

        self.packet_processor._ip_port_buffer[call_id].append(
            ParticipantInfo(
                user="from_user",
                ip_address="10.0.0.0",
                media_port=123456,
                server_ip=self.server_ip,
                server_port=98765,
            )
        )

        result = self.packet_processor._call_ready(call_id)

        self.assertTrue(result)

    def test_check_dup_packet(self):
        """Test that duplicate packets are detected correctly."""

        sip_packet = get_sip_sample_data("invite_incoming")
        sip_layer = get_layer(sip_packet, 'sip')

        # Check the first packet if it is considered duplicate
        result1 = self.packet_processor._check_dup_packet(sip_layer, sip_packet)
        self.assertFalse(result1, "Packet should not be considered duplicate on first check")

        # Check the same packet with identical attributes if it is considered duplicate
        result2 = self.packet_processor._check_dup_packet(sip_layer, sip_packet)
        self.assertTrue(result2, "Same packet should be considered duplicate on second check")

        sip_packet = get_sip_sample_data("200_invite_incoming")
        sip_layer = get_layer(sip_packet, 'sip')

        # Create a new mock packet with the same call_id but different attributes
        result3 = self.packet_processor._check_dup_packet(sip_layer, sip_packet)
        self.assertFalse(result3, "Different packet should not be considered duplicate")

        # Check the same packet with identical attributes if it is considered duplicate
        result4 = self.packet_processor._check_dup_packet(sip_layer, sip_packet)
        self.assertTrue(result4, "Same packet with different attributes should be considered duplicate")

    #=====================================================
    #   Helper methods for checking data and messages
    #=====================================================

    def check_data_in_buffer(self, sip_layer):
        """Check that the data is stored in the buffer correctly."""
        call_id = get_call_id(sip_layer)
        from_user = get_from_user(sip_layer)

        self.assertIn(call_id, self.packet_processor._ip_port_buffer)
        participant_info = self.packet_processor._ip_port_buffer[call_id][0]
        self.assertEqual(participant_info.user, from_user)

    def check_participant_message(self, message, sip_layer):
        """Check that the participant message is published correctly."""

        call_id = get_call_id(sip_layer)
        media_port = int(get_media_port(sip_layer))
        mime_type, sample_rate = get_preferred_codec_sample_rate(sip_layer)
        from_user = get_from_user(sip_layer)
        sdp_connection_info_address = get_sdp_connection_info_address(sip_layer)

        second_args = json.loads(message.args[0])
        second_kwargs = message.kwargs

        self.assertEqual(second_kwargs['exchange_name'], "PARTICIPANTS")
        self.assertEqual(second_kwargs['routing_key'], "participation")

        self.assertEqual(second_args["call_id"], call_id)
        self.assertEqual(second_args["user"], from_user)
        self.assertEqual(second_args["ip_address"], sdp_connection_info_address)
        self.assertEqual(second_args["media_port"], media_port)
        self.assertEqual(second_args["mime_type"], mime_type)

