import threading

from cachetools import TTLCache

from datastructure.dataclass import Call, Participant, EventType
from my_logging.log_config import eventbus_logger, app_logger

cache = TTLCache(maxsize=1000, ttl=60)
cache_lock = threading.Lock()

# TODO filtering of duplications
def sip_process(sip_packet, eventbus):
    sip = sip_packet.sip
    #print(sip.field_names)

    if check_dup_packet(sip):
        return

    if hasattr(sip, 'request_line'):
        if sip.method == 'INVITE':
            app_logger.debug(
                f"INVITE detected: {sip.method},"
                f" Call-ID: {sip.call_id},"
                f" Media Port: {sip.sdp_media_port},"
                f" MIME Type: {sip.sdp_mime_type},"
                f" from user: {sip.from_user}"
            )

            # calling people
            eventbus.publish(Call(type = EventType.NEW_CALL, call_id = sip.call_id,))

            eventbus.publish(
                Participant(
                    type = EventType.PARTICIPANTS,
                    call_id = sip.call_id,
                    user = sip.from_user,
                    media_port = sip.sdp_media_port,
                    mime_type = sip.sdp_mime_type,
                )
            )

        elif sip.method == 'ACK':
            app_logger.debug(f"ACK detected: {sip.method}, Call-ID: {sip.call_id}")

            # Call is established
            eventbus.publish(
                Call(
                    type = EventType.ACK,
                    call_id = sip.call_id,
                    start_time=sip_packet.sniff_time,
                )
            )

            print(sip.method)
        elif sip.method == 'BYE':
            #app_logger.debug(f"BYE detected: {sip.method}")
            # Request to end the call
            print(sip.method)


    elif hasattr(sip, 'status_line'):
       if int(sip.status_code) == 200:
            method = getattr(sip, 'cseq_method', 'UNKNOWN')
            if method == 'INVITE':
                app_logger.debug(
                    f"INVITE accepted: {sip.status_line},"
                    f" Call-ID: {sip.call_id},"
                    f" Media Port: {sip.sdp_media_port},"
                    f" MIME Type: {sip.sdp_mime_type},"
                    f" from user: {sip.to_user}"
                )

                # call setup is confirmed
                eventbus.publish(
                    Participant(
                        type=EventType.PARTICIPANTS,
                        call_id=sip.call_id,
                        user=sip.to_user,
                        media_port=sip.sdp_media_port,
                        mime_type=sip.sdp_mime_type,
                    )
                )

                print(f"{sip.status_code}: {sip.status_line} INVITE")

            elif method == 'BYE':
                app_logger.debug(f"BYE accepted: {sip.status_line}, Call-ID: {sip.call_id}")

                # confirms that the call has ended
                eventbus.publish(
                    Call(
                        type = EventType.CALL_END,
                        call_id = sip.call_id,
                        end_time= sip_packet.sniff_time,
                    )
                )

                print(f"{sip.status_code}: {sip.status_line} BYE")

       elif int(sip.status_code) == 603:
           app_logger.debug(f"Decline detected: {sip.status_line}, Call-ID: {sip.call_id}")

           eventbus.publish(
               Call(
                   type = EventType.CALL_DECLINE,
                   call_id = sip.call_id,
               )
           )

           print(f"{sip.status_code}: {sip.status_line} DECLINE")



# TODO implement rtp processing
def rtp_process(rtp_packet, eventbus):
    pass


# True is when the packet exists in the cache - false if the packet isn't in the cache
def check_dup_packet(sip):
    status_code = getattr(sip, 'status_code', None)
    method = getattr(sip, 'method', None)
    # create the cache name
    unique_cache_id = f"{sip.call_id}-{sip.via_branch}-{status_code if status_code is not None else method}"

    # check in the cache
    with cache_lock:
        if unique_cache_id not in cache:
            cache[unique_cache_id] = True
            return False

    # for key, value in cache.items():
    #     print(f"{key}: {value}")

    return True
