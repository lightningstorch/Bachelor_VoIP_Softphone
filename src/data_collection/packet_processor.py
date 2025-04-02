from datetime import datetime

from Datastructure.dataclass import Call, Participant, EventType
from my_logging.log_config import eventbus_logger, app_logger


# TODO implement sip processing
def sip_process(sip_packet, eventbus):
    sip = sip_packet.sip
    #print(sip.field_names)

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
                    type = EventType.CALL_STARTED,
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

                print(f"{sip.status_code}: {sip.status_line} invite")

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


# TODO implement rtp processing
def rtp_process(rtp_packet, eventbus):
    pass

