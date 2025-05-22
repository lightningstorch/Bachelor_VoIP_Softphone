import json
import threading

from collections import deque, defaultdict
from dataclasses import asdict
from queue import Empty
from typing import Tuple

from aio_pika import ExchangeType
from cachetools import TTLCache

from call_context.manager_call_context import ManagerCallContext
from config.config import server_ip
from datastructure.dataclass_models import Call, Participant, EventType, ServerInfo, ParticipantInfo
from my_logging.log_config import app_logger


class PacketProcessor(threading.Thread):
    def __init__(self, message_service, queue, manager_call_context: ManagerCallContext):
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
        # Tuple[call_id, user]
        self._call_map: dict[Tuple[str, int, str, int], Tuple[str, str]] = {}
        # Tuple[ssrc, call_id, user]
        self._ssrc_to_call_id: dict[str, Tuple[str, str]] = {}

    def set_context_ready(self):
        self._context_ready.set()

    def stop(self):
        self._stop_event.set()

    def run(self):
        app_logger.debug("Starting packet processor thread")
        print("Starting packet processor thread")

        while not self._stop_event.is_set():

            try:
                packet = self.queue.get(timeout=1)
            except Empty:
                continue

            if hasattr(packet, 'sip'):
                #print("SIP packet detected")
                self._sip_process(packet)

            elif hasattr(packet, 'rtp') and packet.ip.dst == server_ip:
                print(f"RTP packet detected SSRC: {packet.rtp.ssrc} - Seq: {packet.rtp.seq}")
                self._rtp_process(packet)

    def _sip_process(self, sip_packet):
        sip = sip_packet.sip
        #print(sip.field_names)

        # Cache packets to avoid duplicate processing - duplicate on the network
        if self.check_dup_packet(sip, sip_packet):
            return

        if sip_packet.ip.dst == server_ip:
            # incoming packets from the server
            if hasattr(sip, 'request_line'):
                match sip.method:
                    case 'INVITE': self._sip_incoming_invite(sip)

                    case 'ACK': self._sip_incoming_ack(sip, sip_packet)

                    case 'BYE': print(sip.method)
                        # app_logger.debug(f"BYE detected: {sip.method}")
                        # Request to end the call

            elif hasattr(sip, 'status_line'):
               if int(sip.status_code) == 200:
                    method = getattr(sip, 'cseq_method', 'UNKNOWN')

                    if method == 'INVITE':
                        self._sip_incoming_200_invite(sip)

                    elif method == 'BYE':
                        self._sip_incoming_200_bye(sip, sip_packet)

               elif int(sip.status_code) == 603:
                   # 603 = Decline
                   self._sip_incoming_603_decline(sip)
        else:
            # outing packets from the server
            if hasattr(sip, 'request_line') and sip.method == 'INVITE':
                self._sip_outgoing_invite(sip)
            elif hasattr(sip, 'status_line') and int(sip.status_code) == 200 and getattr(sip, 'cseq_method', 'UNKNOWN') == 'INVITE':
                self._sip_outgoing_200_invite(sip)

    def _rtp_process(self, rtp_packet):
        rtp = rtp_packet.rtp
        # print(rtp.field_names)

        key = (rtp_packet.ip.src, rtp_packet.udp.srcport, rtp_packet.ip.dst, rtp_packet.udp.dstport)

        call_id, user = self._call_map[key]

        if rtp.ssrc not in self._ssrc_to_call_id:
            # store the SSRC in the call_map
            self._ssrc_to_call_id[rtp.ssrc] = (call_id, user)

            # send the ssrc to aggregator to store in database
            self._message_service.publish(
                json.dumps({
                    "call_id": call_id,
                    "ssrc": rtp.ssrc,
                    "user": user
                })
                ,
                exchange_name="SSRC",
                exchange_type=ExchangeType.DIRECT,
                routing_key="ssrc",
            )

        #binary_value = rtp.payload.binary_value
        self.manager_call_context.enqueue_packet(call_id, rtp.ssrc, rtp_packet)

    # TODO reduce the code duplication

    def _sip_incoming_invite(self, sip):
        app_logger.debug(
            f"INVITE detected: {sip.method},"
            f" Call-ID: {sip.call_id},"
            f" Media Port: {sip.sdp_media_port},"
            f" MIME Type: {sip.sdp_mime_type},"
            f" user: {sip.from_user}"
        )

        payload_call = Call(type=EventType.NEW_CALL, call_id=sip.call_id).model_dump_json()

        self._message_service.publish(
            payload_call,
            exchange_name="NEW_CALL",
            exchange_type=ExchangeType.DIRECT,
            routing_key="new_call",
        )

        payload_participants = Participant(
            type=EventType.PARTICIPANTS,
            call_id=sip.call_id,
            user=sip.from_user,
            ip_address=sip.sdp_connection_info_address,
            media_port=sip.sdp_media_port,
            mime_type=sip.sdp_mime_type,
        ).model_dump_json()

        self._message_service.publish(
            payload_participants,
            exchange_name="PARTICIPANTS",
            exchange_type=ExchangeType.DIRECT,
            routing_key="participation",
        )

        # store in buffer for RTP processing
        fields = {
            "user": sip.from_user,
            "ip_address": sip.sdp_connection_info_address,
            "media_port": sip.sdp_media_port,
            "mime_type": sip.sdp_mime_type,
        }
        self._store_in_buffer(sip.call_id, **fields)

    def _sip_incoming_200_invite(self, sip):
        # call setup is confirmed
        print(f"{sip.status_code}: {sip.status_line} INVITE")

        app_logger.debug(
            f"INVITE accepted: {sip.status_line},"
            f" Call-ID: {sip.call_id},"
            f" Media Port: {sip.sdp_media_port},"
            f" MIME Type: {sip.sdp_mime_type},"
            f" user: {sip.to_user}"
        )

        payload_invite = Participant(
            type=EventType.PARTICIPANTS,
            call_id=sip.call_id,
            user=sip.to_user,
            ip_address=sip.sdp_connection_info_address,
            media_port=sip.sdp_media_port,
            mime_type=sip.sdp_mime_type,
        ).model_dump_json()

        self._message_service.publish(
            payload_invite,
            exchange_name="PARTICIPANTS",
            exchange_type=ExchangeType.DIRECT,
            routing_key="participation",
        )

        # store in buffer for RTP processing
        fields = {
            "user": sip.to_user,
            "ip_address": sip.sdp_connection_info_address,
            "media_port": sip.sdp_media_port,
            "mime_type": sip.sdp_mime_type,
        }
        self._store_in_buffer(sip.call_id, **fields)

    def _sip_incoming_ack(self, sip, sip_packet):
        print(sip.method)

        app_logger.debug(f"ACK detected: {sip.method}, Call-ID: {sip.call_id}")

        payload_ack = Call(
            type = EventType.ACK,
            call_id = sip.call_id,
            start_time=sip_packet.sniff_time,
        ).model_dump_json()

        self._message_service.publish(
            payload_ack,
            exchange_name="ACK",
            exchange_type=ExchangeType.DIRECT,
            routing_key="ack",
        )

    def _sip_incoming_200_bye(self, sip, sip_packet):
        print(f"{sip.status_code}: {sip.status_line} BYE")

        app_logger.debug(f"BYE accepted: {sip.status_line}, Call-ID: {sip.call_id}")

        payload_bye= Call(
            type = EventType.CALL_END,
            call_id = sip.call_id,
            end_time= sip_packet.sniff_time,
        ).model_dump_json()

        self._message_service.publish(
            payload_bye,
            exchange_name="CALL_END",
            exchange_type=ExchangeType.DIRECT,
            routing_key="end_call",
        )

        self.remove_from_buffer(sip.call_id)

    def _sip_incoming_603_decline(self, sip):
        print(f"{sip.status_code}: {sip.status_line} DECLINE")

        app_logger.debug(f"Decline detected: {sip.status_line}, Call-ID: {sip.call_id}")

        payload_decline= Call(
            type = EventType.CALL_DECLINE,
            call_id = sip.call_id,
        ).model_dump_json()

        self._message_service.publish(
            payload_decline,
            exchange_name="CALL_DECLINE",
            exchange_type=ExchangeType.DIRECT,
            routing_key="call_decline",
        )

    def _sip_outgoing_invite(self, sip):
        payload_server_data = ServerInfo(
            type=EventType.SERVER_INFO,
            call_id=sip.call_id,
            server_ip=sip.sdp_connection_info_address,
            server_port=sip.sdp_media_port,
            user=sip.to_user,
        ).model_dump_json()

        self._message_service.publish(
            payload_server_data,
            exchange_name="SERVER_INFO",
            exchange_type=ExchangeType.DIRECT,
            routing_key="server_info",
        )

        # store in buffer for RTP processing
        fields = {
            "user": sip.to_user,
            "server_ip": sip.sdp_connection_info_address,
            "server_port": sip.sdp_media_port
        }
        self._store_in_buffer(sip.call_id, **fields)

    def _sip_outgoing_200_invite(self, sip):
        payload_server_data = ServerInfo(
            type=EventType.SERVER_INFO,
            call_id=sip.call_id,
            server_ip=sip.sdp_connection_info_address,
            server_port=sip.sdp_media_port,
            user=sip.from_user,
        ).model_dump_json()

        self._message_service.publish(
            payload_server_data,
            exchange_name="SERVER_INFO",
            exchange_type=ExchangeType.DIRECT,
            routing_key="server_info",
        )

        # store in buffer for RTP processing
        fields = {
            "user": sip.from_user,
            "server_ip": sip.sdp_connection_info_address,
            "server_port": sip.sdp_media_port
        }
        self._store_in_buffer(sip.call_id, **fields)

    # =========================================================
    #                   Helper Methods
    # =========================================================

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

    def remove_from_buffer(self, call_id: str):
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

    def check_dup_packet(self, sip, sip_packet):
        """
        To avoid duplicate processing of packets, we cache the packets in a cache.
        Sometimes the package is duplicated in the network.

        :param cache_lock: To lock the cache for writing
        :param cache: cache for the SIP packets
        :param sip_packet: Network packet from the Network dump
        :param sip: Session Initiation Protocol packet from the Network dump
        :return: True is when the packet exists in the cache - false if the packet isn't in the cache
        """
        status_code = getattr(sip, 'status_code', None)
        method = getattr(sip, 'method', None)

        # create the cache name
        unique_cache_id = (f"{sip.call_id}"
                           f"-{sip.via_branch}"
                           f"-{status_code if status_code is not None else method}"
                           f"-{sip_packet.ip.src}"
                           f"-{sip_packet.udp.srcport}")

        # check in the cache
        with self._cache_lock:
            if unique_cache_id not in self._cache:
                self._cache[unique_cache_id] = True
                return False

        # print the cache for debugging
        # for key, value in cache.items():
        #     print(f"{key}: {value}")

        return True
