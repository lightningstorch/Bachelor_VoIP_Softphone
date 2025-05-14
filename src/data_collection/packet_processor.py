import json
import threading
import time
from dataclasses import asdict

from aio_pika import ExchangeType
from cachetools import TTLCache

from datastructure.dataclass_models import Call, Participant, EventType
from my_logging.log_config import app_logger


# Cache for the Session Initiation Protocol
cache = TTLCache(maxsize=1000, ttl=60)
cache_lock = threading.Lock()

def process_packets(packet, message_service, context_ready):

    if 'SIP' in packet:
        print("SIP packet detected")
        app_logger.debug("SIP packet detected")

        sip_process(packet, message_service)

    # elif 'RTP' in packet:
        # print("RTP packet detected")
        # app_logger.debug("RTP packet detected")
        #
        # # wait until context stuff is ready
        # context_ready.wait()
        #
        # rtp_process(packet, eventbus)

# TODO filtering of duplications
def sip_process(sip_packet, message_service):
    sip = sip_packet.sip
    #print(sip.field_names)

    # Cache packets to avoid duplicate processing - duplicate on the network
    if check_dup_packet(sip):
        return

    if hasattr(sip, 'request_line'):
        match sip.method:
            case 'INVITE': sip_invite(message_service, sip)

            case 'ACK': sip_ack(message_service, sip, sip_packet)

            case 'BYE': print(sip.method)
                # app_logger.debug(f"BYE detected: {sip.method}")
                # Request to end the call

    elif hasattr(sip, 'status_line'):
       if int(sip.status_code) == 200:
            method = getattr(sip, 'cseq_method', 'UNKNOWN')

            if method == 'INVITE':
                sip_200_invite(message_service, sip)

            elif method == 'BYE':
                sip_200_bye(message_service, sip, sip_packet)

       elif int(sip.status_code) == 603:
           # 603 = Decline
           sip_603_decline(message_service, sip)


# TODO implement rtp processing
def rtp_process(rtp_packet, message_service):
    pass


def sip_invite(message_service, sip):
    app_logger.debug(
        f"INVITE detected: {sip.method},"
        f" Call-ID: {sip.call_id},"
        f" Media Port: {sip.sdp_media_port},"
        f" MIME Type: {sip.sdp_mime_type},"
        f" from user: {sip.from_user}"
    )

    payload_call = Call(type=EventType.NEW_CALL, call_id=sip.call_id).model_dump_json()

    message_service.publish(
        payload_call,
        exchange_name="NEW_CALL",
        exchange_type=ExchangeType.DIRECT,
        routing_key="new_call",
    )

    payload_participants = Participant(
        type=EventType.PARTICIPANTS,
        call_id=sip.call_id,
        user=sip.from_user,
        media_port=sip.sdp_media_port,
        mime_type=sip.sdp_mime_type,
    ).model_dump_json()

    message_service.publish(
        payload_participants,
        exchange_name="PARTICIPANTS",
        exchange_type=ExchangeType.DIRECT,
        routing_key="participation",
    )

def sip_ack(message_service, sip, sip_packet):
    print(sip.method)

    app_logger.debug(f"ACK detected: {sip.method}, Call-ID: {sip.call_id}")

    payload_ack = Call(
        type = EventType.ACK,
        call_id = sip.call_id,
        start_time=sip_packet.sniff_time,
    ).model_dump_json()

    message_service.publish(
        payload_ack,
        exchange_name="ACK",
        exchange_type=ExchangeType.DIRECT,
        routing_key="ack",
    )


def sip_200_invite(message_service, sip):
    # call setup is confirmed
    print(f"{sip.status_code}: {sip.status_line} INVITE")

    app_logger.debug(
        f"INVITE accepted: {sip.status_line},"
        f" Call-ID: {sip.call_id},"
        f" Media Port: {sip.sdp_media_port},"
        f" MIME Type: {sip.sdp_mime_type},"
        f" from user: {sip.to_user}"
    )

    payload_invite = Participant(
        type=EventType.PARTICIPANTS,
        call_id=sip.call_id,
        user=sip.to_user,
        media_port=sip.sdp_media_port,
        mime_type=sip.sdp_mime_type,
    ).model_dump_json()
    print("time is waiting")

    message_service.publish(
        payload_invite,
        exchange_name="PARTICIPANTS",
        exchange_type=ExchangeType.DIRECT,
        routing_key="participation",
    )


def sip_200_bye(message_service, sip, sip_packet):
    print(f"{sip.status_code}: {sip.status_line} BYE")

    app_logger.debug(f"BYE accepted: {sip.status_line}, Call-ID: {sip.call_id}")

    payload_bye= Call(
        type = EventType.CALL_END,
        call_id = sip.call_id,
        end_time= sip_packet.sniff_time,
    ).model_dump_json()

    message_service.publish(
        payload_bye,
        exchange_name="CALL_END",
        exchange_type=ExchangeType.DIRECT,
        routing_key="end_call",
    )


def sip_603_decline(message_service, sip):
    print(f"{sip.status_code}: {sip.status_line} DECLINE")

    app_logger.debug(f"Decline detected: {sip.status_line}, Call-ID: {sip.call_id}")

    payload_decline= Call(
        type = EventType.CALL_DECLINE,
        call_id = sip.call_id,
    ).model_dump_json()

    message_service.publish(
        payload_decline,
        exchange_name="CALL_DECLINE",
        exchange_type=ExchangeType.DIRECT,
        routing_key="call_decline",
    )


def check_dup_packet(sip):
    """
    To avoid duplicate processing of packets, we cache the packets in a cache.
    Sometimes the package is duplicated in the network.

    :param sip: Session Initiation Protocol packet from the Network dump
    :return: True is when the packet exists in the cache - false if the packet isn't in the cache
    """
    status_code = getattr(sip, 'status_code', None)
    method = getattr(sip, 'method', None)
    # create the cache name
    unique_cache_id = f"{sip.call_id}-{sip.via_branch}-{status_code if status_code is not None else method}"

    # check in the cache
    with cache_lock:
        if unique_cache_id not in cache:
            cache[unique_cache_id] = True
            return False

    # print the cache for debugging
    # for key, value in cache.items():
    #     print(f"{key}: {value}")

    return True
