import json
import threading

from collections import deque, defaultdict
from dataclasses import asdict
from queue import Empty, Queue
from typing import Tuple
from aio_pika import ExchangeType
from cachetools import TTLCache
from call_context.manager_call_context import ManagerCallContext
from config.config import server_ip
from datastructure.dataclass_models import Call, Participant, EventType, ServerInfo, ParticipantInfo
from utils.packet_parsing import *

class PacketProcessor(threading.Thread):
    def __init__(self, message_service, queue: Queue, manager_call_context: ManagerCallContext, cleanup_queue: Queue):
        super().__init__()
        self.daemon = True
        self._stop_event = threading.Event()
        self._context_ready = threading.Event()
        self.queue = queue
        self._message_service = message_service
        self.manager_call_context = manager_call_context

        # Cache for the Session Initiation Protocol to avoid duplicate processing
        self._cache = TTLCache(maxsize=1000, ttl=60)
        self._cache_lock = threading.Lock()

        self._waiting_rtp = deque()
        self._flushed_initial = False

        # Call context buffer to store the information for rtp processing
        self._ip_port_buffer: dict[str, list[ParticipantInfo]] = defaultdict(list)
        # Tuple[ip, port, ip, port], Tuple[call_id, user]
        self._call_map: dict[Tuple[str, int, str, int], Tuple[str, str]] = {}
        # Tuple[ssrc, Tuple[call_id, user]]
        self._ssrc_to_call_id: dict[str, Tuple[str, str]] = {}
        # Queue for cleanup of old call contexts
        self.cleanup_queue = cleanup_queue
        # Buffer for RTP packets
        self._rtp_buffer: dict[tuple, list] = defaultdict(list)

    def set_context_ready(self):
        self._context_ready.set()

    def stop(self):
        self._stop_event.set()

    def run(self):
        app_logger.debug("Starting packet processor thread")
        print("Starting packet processor thread")

        while not self._stop_event.is_set():

            # cleanup old call contexts
            try:
                cleanup_id = self.cleanup_queue.get_nowait()
            except Empty:
                pass
            else:
                app_logger.debug(f"Cleanup call context for call_id: {cleanup_id}")
                self._clear_call_resources(cleanup_id)

            try:
                packet = self.queue.get(timeout=0.001)
            except Empty:
                continue

            sip_layer = get_layer(packet, "sip")
            rtp_layer = get_layer(packet, "rtp")
            ip_dst = get_ip_dst(packet)

            if sip_layer is not None:
                self._sip_process(packet, sip_layer)

            elif rtp_layer is not None and ip_dst == server_ip:
                self._rtp_process(packet)

    def _sip_process(self, sip_packet, sip):

        # Cache packets to avoid duplicate processing - duplicate on the network
        if self._check_dup_packet(sip, sip_packet):
            return

        ip_layer = get_layer(sip_packet, "ip")

        if ip_layer.get('ip.dst') == server_ip:
            # incoming packets from the server
            if 'sip.Request-Line' in sip:

                method = get_method(sip)

                match method:
                    case 'INVITE': self._sip_incoming_invite(sip)

                    case 'ACK': self._sip_incoming_ack(sip, sip_packet)

                    case 'BYE': print(method)
                        # app_logger.debug(f"BYE detected: {sip.method}")
                        # Request to end the call

            elif 'sip.Status-Line' in sip:

                status_code = get_status_code(sip)

                if status_code and int(status_code) == 200:

                    cseq_method = get_cseq_method(sip)

                    if cseq_method == 'INVITE':
                        self._sip_incoming_200_invite(sip)

                    elif cseq_method == 'BYE':
                        self._sip_incoming_200_bye(sip, sip_packet)

                elif status_code and int(status_code) == 603:
                    # 603 = Decline
                    self._sip_incoming_603_decline(sip)

        else:
            # outing packets from the server
            if 'sip.Request-Line' in sip:

                method = get_method(sip)

                if method == 'INVITE':
                    to_user = get_to_user(sip)
                    self._outgoing_invite(sip, to_user)

            elif 'sip.Status-Line' in sip:

                status_code = get_status_code(sip)
                cseq_method = get_cseq_method(sip)

                if status_code and int(status_code) == 200 and cseq_method == 'INVITE':
                    from_user = get_from_user(sip)
                    self._outgoing_invite(sip, from_user)

    def _rtp_process(self, rtp_packet):

        ip_src = get_ip_src(rtp_packet)
        udp_srcport = get_udp_srcport(rtp_packet)
        ip_dst = get_ip_dst(rtp_packet)
        udp_dstport = get_udp_dstport(rtp_packet)

        key = (ip_src, udp_srcport, ip_dst, udp_dstport)

        if key not in self._call_map:
            app_logger.debug(f"RTP-paket without mapping: {key} -> buffer length = {len(self._rtp_buffer[key]) + 1}")
            self._rtp_buffer[key].append(rtp_packet)
            return

        call_id, user = self._call_map[key]

        buffered = self._rtp_buffer.pop(key, [])
        for packet in buffered:
            self._handle_rtp_packet(packet, call_id, user)

        self._handle_rtp_packet(rtp_packet, call_id, user)


    # =========================================================
    #                   SIP Methods
    # =========================================================

    def _sip_incoming_invite(self, sip):

        method = get_method(sip)
        call_id = get_call_id(sip)
        media_port = get_media_port(sip)
        mime_type, sample_rate = get_preferred_codec_sample_rate(sip)
        from_user = get_from_user(sip)


        app_logger.debug(
            f"INVITE detected: {method},"
            f" Call-ID: {call_id},"
            f" Media Port: {media_port},"
            f" MIME Type: {mime_type},"
            f" user: {from_user}"
        )

        payload_call = Call(
            type=EventType.NEW_CALL,
            caller=from_user,
            call_id=call_id
        ).model_dump_json()

        self._message_service.publish(
            payload_call,
            exchange_name="NEW_CALL",
            exchange_type=ExchangeType.DIRECT,
            routing_key="new_call",
        )

        self._publish_and_store_participant(sip, from_user)

    def _sip_incoming_200_invite(self, sip):
        # call setup is confirmed

        status_line = get_status_line(sip)
        call_id = get_call_id(sip)
        media_port = get_media_port(sip)
        to_user = get_to_user(sip)
        mime_type, sample_rate = get_preferred_codec_sample_rate(sip)

        app_logger.debug(
            f"INVITE accepted: {status_line},"
            f" Call-ID: {call_id},"
            f" Media Port: {media_port},"
            f" MIME Type: {mime_type},"
            f" user: {to_user}"
        )

        self.manager_call_context.create_or_insert_call_context(
            call_id=call_id,
            sample_rate=int(sample_rate)
        )

        self._publish_and_store_participant(sip, to_user)

    def _sip_incoming_ack(self, sip, sip_packet):
        method = get_method(sip)
        call_id = get_call_id(sip)
        time_stamp = get_time_stamp_isoformat(sip_packet)

        print(method)

        app_logger.debug(f"ACK detected: {method}, Call-ID: {call_id}")

        payload_ack = Call(
            type = EventType.ACK,
            call_id = call_id,
            start_time=time_stamp,
        ).model_dump_json()

        self._message_service.publish(
            payload_ack,
            exchange_name="ACK",
            exchange_type=ExchangeType.DIRECT,
            routing_key="ack",
        )

    def _sip_incoming_200_bye(self, sip, sip_packet):

        call_id = get_call_id(sip)
        status_code = get_status_code(sip)
        status_line = get_status_line(sip)
        time_stamp = get_time_stamp_isoformat(sip_packet)

        print(f"{status_code}: {status_line} BYE")

        app_logger.debug(f"BYE accepted: {status_line}, Call-ID: {call_id}")

        payload_bye= Call(
            type = EventType.CALL_END,
            call_id = call_id,
            end_time= time_stamp,
        ).model_dump_json()

        self._message_service.publish(
            payload_bye,
            exchange_name="CALL_END",
            exchange_type=ExchangeType.DIRECT,
            routing_key="end_call",
        )

        self.manager_call_context.end_call(call_id)

    def _sip_incoming_603_decline(self, sip):
        call_id = get_call_id(sip)
        status_code = get_status_code(sip)
        status_line = get_status_line(sip)

        print(f"{status_code}: {status_line} DECLINE")

        app_logger.debug(f"Decline detected: {status_line}, Call-ID: {call_id}")

        payload_decline= Call(
            type = EventType.CALL_DECLINE,
            call_id = call_id,
        ).model_dump_json()

        self._message_service.publish(
            payload_decline,
            exchange_name="CALL_DECLINE",
            exchange_type=ExchangeType.DIRECT,
            routing_key="call_decline",
        )

    def _outgoing_invite(self, sip, user):
        self._send_server_info(sip, user)

        call_id = get_call_id(sip)
        sdp_connection_info_address = get_sdp_connection_info_address(sip)
        media_port = get_media_port(sip)

        # store in buffer for RTP processing
        fields = {
            "user": user,
            "server_ip": sdp_connection_info_address,
            "server_port": media_port
        }
        self._store_in_buffer(call_id, **fields)

    # =========================================================
    #                   Helper Methods
    # =========================================================

    def _send_server_info(self, sip, user):
        call_id = get_call_id(sip)
        sdp_connection_info_address = get_sdp_connection_info_address(sip)
        media_port = get_media_port(sip)

        payload_server_data = ServerInfo(
            type=EventType.SERVER_INFO,
            call_id=call_id,
            server_ip=sdp_connection_info_address,
            server_port=media_port,
            user=user,
        ).model_dump_json()

        self._message_service.publish(
            payload_server_data,
            exchange_name="SERVER_INFO",
            exchange_type=ExchangeType.DIRECT,
            routing_key="server_info",
        )

    def _handle_rtp_packet(self, rtp_packet, call_id, user):

        ssrc = get_ssrc(rtp_packet)

        if ssrc not in self._ssrc_to_call_id:
            # store the SSRC in the call_map
            self._ssrc_to_call_id[ssrc] = (call_id, user)

            # send the ssrc to aggregator to store in database
            self._message_service.publish(
                json.dumps({
                    "call_id": call_id,
                    "ssrc": ssrc,
                    "user": user
                })
                ,
                exchange_name="SSRC",
                exchange_type=ExchangeType.DIRECT,
                routing_key="ssrc",
            )

        #binary_value = rtp.payload.binary_value
        self.manager_call_context.enqueue_packet(call_id, ssrc, rtp_packet)

    def _publish_and_store_participant(self, sip, user):

        call_id = get_call_id(sip)
        sdp_connection_info_address = get_sdp_connection_info_address(sip)
        media_port = get_media_port(sip)
        mime_type, _ = get_preferred_codec_sample_rate(sip)

        payload_participants = Participant(
            type=EventType.PARTICIPANTS,
            call_id=call_id,
            user=user,
            ip_address=sdp_connection_info_address,
            media_port=media_port,
            mime_type=mime_type,
        ).model_dump_json()

        self._message_service.publish(
            payload_participants,
            exchange_name="PARTICIPANTS",
            exchange_type=ExchangeType.DIRECT,
            routing_key="participation",
        )

        # store in buffer for RTP processing
        fields = {
            "user": user,
            "ip_address": sdp_connection_info_address,
            "media_port": media_port,
            "mime_type": mime_type,
        }

        self._store_in_buffer(call_id, **fields)

    def _store_in_buffer(self, call_id: str, **fields):
        """
        Store the IP and port from the client and server in the buffer.
        After the call is full of the data, it will be inserted in the call_map
        :param call_id: id from the call
        :param fields: fields of the connection between client and server
        """
        if not self._ip_port_buffer[call_id]:
            self._ip_port_buffer[call_id] = []

        participant_info = next((p for p in self._ip_port_buffer[call_id] if p.user == fields["user"]), None)

        if not participant_info:
            participant_info = ParticipantInfo(user=fields["user"])
            self._ip_port_buffer[call_id].append(participant_info)

        for key, value in fields.items():
            setattr(participant_info, key, value)

        # switch the data from buffer to call_map for rtp categorisation
        if self._call_ready(call_id):
            participants_list = self._ip_port_buffer.get(call_id)
            for p in participants_list:
                key = (p.ip_address, p.media_port, p.server_ip, p.server_port)
                self._call_map[key] = (call_id, p.user)

    def _clear_call_resources(self, call_id: str):
        """
        Remove the call from the buffers
        :param call_id: id from the call
        """
        if call_id in self._ip_port_buffer:
            participants_list = self._ip_port_buffer.pop(call_id)
            for p in participants_list:
                key = (p.ip_address, p.media_port, p.server_ip, p.server_port)
                self._call_map.pop(key)

            for key, (call, user) in list(self._ssrc_to_call_id.items()):
                if call == call_id:
                    self._ssrc_to_call_id.pop(key)

        app_logger.debug(f"Cleared resources for call_id: {call_id}")

    def _call_ready(self, call_id: str) -> bool:
        """
        Check if the call is ready to switch the buffer
        :param call_id: id from the call
        :return: True if the call is ready - False if not
        """
        participants = self._ip_port_buffer.get(call_id, [])

        if len(participants) < 2:
            return False

        required = ("ip_address", "media_port", "server_ip", "server_port")
        for p in participants:
            data = asdict(p)
            for field in required:
                if field not in data or data[field] is None:
                    return False

        return True

    def _check_dup_packet(self, sip, sip_packet):
        """
        To avoid duplicate processing of packets, we cache the packets in a cache.
        Sometimes the package is duplicated in the network.

        :param cache_lock: To lock the cache for writing
        :param cache: cache for the SIP packets
        :param sip_packet: Network packet from the Network dump
        :param sip: Session Initiation Protocol packet from the Network dump
        :return: True is when the packet exists in the cache - false if the packet isn't in the cache
        """
        status_code = sip.get('sip.Status-Line_tree')
        if status_code:
            status_code = status_code.get('sip.Status-Code')

        method = sip.get('sip.Request-Line_tree')
        if method:
            method.get('sip.Method')

        action = status_code or method

        call_id = get_call_id(sip)
        via_branch = get_via_branches(sip)

        ip_src = get_ip_src(sip_packet)

        udp_srcport = get_udp_srcport(sip_packet)



        # create the cache name
        unique_cache_id = (f"{call_id}"
                           f"-{via_branch}"
                           f"-{action}"
                           f"-{ip_src}"
                           f"-{udp_srcport}")

        # check in the cache
        with self._cache_lock:
            if unique_cache_id not in self._cache:
                self._cache[unique_cache_id] = True
                return False

        # print the cache for debugging
        # for key, value in cache.items():
        #     print(f"{key}: {value}")

        return True




