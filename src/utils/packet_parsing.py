import datetime

from typing import OrderedDict
from my_logging.log_config import app_logger

"""
This module provides utility functions for parsing and extracting information from network packets.
It includes methods to retrieve specific layers, codec information, media ports, connection info,
SIP message details, and various packet attributes such as timestamps, IP addresses, UDP ports,
SSRC, RTP payload, and Opus frame data.
"""

# =========================================================
#                   Json Methods
# =========================================================

def get_layer(packet: dict, layer_name: str) -> dict | None:
    """
    Get a specific layer from the packet.
    This function retrieves a layer from the packet's source layers.
    :param packet: The packet to get the layer from.
    :param layer_name: The layer name to retrieve.
    :return: The layer dictionary if found, otherwise None.
    """
    try:
        return packet["_source"]["layers"].get(layer_name)
    except (KeyError, AttributeError):
        return None

def get_preferred_codec_sample_rate(sip):
    """
    Get the preferred codec and sample rate from the SDP tree in the SIP message.
    This function checks the SDP tree for the 'opus' codec and returns its sample rate.
    If 'opus' is not found, it returns None for both codec and sample rate.
    :param sip: The SIP message contains the SDP tree.
    :return: The preferred codec and sample rate as a tuple (codec, sample_rate).
    """
    try:
        # Get the SIP message body tree (Windows) or the SIP message body (Linux)
        body = sip.get('sip.msg_body_tree') or sip.get('sip.msg_body', {})
        sdp = body.get('sdp', {})
        attrs = sdp.get('sdp.media_attr_tree', [])

        # search for the 'opus' codec in the media attributes
        for entry in attrs:
            if entry.get('sdp.mime.type') == 'opus':
                return entry.get('sdp.mime.type'), entry.get('sdp.sample_rate')
    except (KeyError, TypeError):
        pass

    return None, None

def get_media_port(sip):
    """
    Get the media port from the SDP tree in the SIP message.
    This function retrieves the media port from the SDP entries in the SIP message body.
    It checks the 'sdp.media_tree' for entries and returns the first found port.
    :param sip: The SIP message contains the SDP tree.
    :return: The media port as an integer if found, otherwise None.
    """

    # Get the SIP message body tree (Windows) or the SIP message body (Linux)
    body = sip.get('sip.msg_body_tree', {}) or sip.get('sip.msg_body', {})
    sdp = body.get('sdp', {})
    entries  = sdp.get('sdp.media_tree', [])

    # Ensure entries is a list, if not make it a list
    if isinstance(entries , dict):
        entries  = [entries ]

    # Iterate through the entries to find the media port
    for entry in entries :
        port = entry.get('sdp.media.port')
        if port:
            return port

    return None

def get_sdp_connection_info_address(sip):
    """
    Get the connection info address from the SDP tree in the SIP message.
    This function retrieves the connection info address from the SDP entries in the SIP message body.
    It checks the 'sdp.connection_info_tree' for entries and returns the first found address.
    :param sip: The SIP message contains the SDP tree.
    :return: The connection info address as a string if found, otherwise None.
    """

    # Get the SIP message body tree (Windows) or the SIP message body (Linux)
    body = sip.get('sip.msg_body_tree') or sip.get('sip.msg_body', {})
    sdp = body.get('sdp', {})
    infos = sdp.get('sdp.connection_info_tree', [])

    # Ensure entries is a list, if not make it a list
    if isinstance(infos, dict):
        infos = [infos]

    # Iterate through the connection info entries to find the address
    for ci in infos:
        addr = ci.get('sdp.connection_info.address')
        if addr:
            return addr

    return None

def get_call_id(sip):
    """
    Get the Call-ID from the SIP message header tree.
    This function retrieves the Call-ID from the SIP message header tree.
    It checks the 'sip.msg_hdr_tree' for the 'sip.Call-ID' field and returns its value.
    :param sip: The SIP message contains the header tree.
    :return: The Call-ID as a string if found, otherwise None.
    """
    try:
        return sip.get('sip.msg_hdr_tree').get('sip.Call-ID')
    except Exception as e:
        return None

def get_from_user(sip):
    """
    Return the From user from the SIP message header tree.
    This function retrieves the From user from the SIP message header tree.
    It checks the 'sip.msg_hdr_tree' for the 'sip.From_tree' and retrieves
    the 'sip.from.addr_tree' and 'sip.from.user' fields.
    :param sip: The SIP message contains the header tree.
    :return: The From user as a string if found, otherwise None.
    """
    try:
        return (sip
                 .get('sip.msg_hdr_tree')
                 .get('sip.From_tree')
                 .get('sip.from.addr_tree')
                 .get('sip.from.user')
                 )
    except Exception as e:
        return None

def get_to_user(sip):
    """
    Return the To user from the SIP message header tree.
    This function retrieves the To user from the SIP message header tree.
    It checks the 'sip.msg_hdr_tree' for the 'sip.To_tree' and retrieves
    the 'sip.to.addr_tree' and 'sip.to.user' fields.
    :param sip: The SIP message contains the header tree.
    :return: The To user as a string if found, otherwise None.
    """
    try:
        return (sip
                 .get('sip.msg_hdr_tree')
                 .get('sip.To_tree')
                 .get('sip.to.addr_tree')
                 .get('sip.to.user')
                 )
    except Exception as e:
        return None

def get_method(sip):
    """
    Return the SIP method from the SIP message header tree.
    This function retrieves the SIP method from the Request-Line tree in the SIP message.
    It checks the 'sip.Request-Line_tree' for the 'sip.Method' field.
    :param sip: The SIP message contains the header tree.
    :return: The SIP method as a string if found, otherwise None.
    """
    try:
        return sip.get('sip.Request-Line_tree').get("sip.Method")
    except Exception as e:
        return None

def get_status_code(sip):
    """
    Return the SIP status code from the SIP message header tree.
    This function retrieves the SIP status code from the Status-Line tree in the SIP message.
    It checks the 'sip.Status-Line_tree' for the 'sip.Status-Code' field.
    :param sip: The SIP message contains the header tree.
    :return: The SIP status code as a string if found, otherwise None.
    """
    try:
        return sip.get('sip.Status-Line_tree').get('sip.Status-Code')
    except Exception as e:
        return None

def get_cseq_method(sip):
    """
    Return the CSeq method from the SIP message header tree.
    This function retrieves the CSeq method from the CSeq tree in the SIP message.
    It checks the 'sip.msg_hdr_tree' for the 'sip.CSeq_tree' and
    retrieves the 'sip.CSeq.method' field.
    :param sip: The SIP message contains the header tree.
    :return: The CSeq method as a string if found, otherwise None.
    """
    try:
        return sip.get('sip.msg_hdr_tree').get('sip.CSeq_tree').get('sip.CSeq.method')
    except Exception as e:
        return None

def get_status_line(sip):
    """
    Return the SIP status line from the SIP message.
    This function retrieves the SIP status line from the Status-Line tree in the SIP message.
    It checks the 'sip.Status-Line' field in the SIP message.
    :param sip: The SIP message contains the header tree.
    :return: The SIP status line as a string if found, otherwise None.
    """
    try:
        return sip.get('sip.Status-Line')
    except Exception as e:
        return None

def get_time_stamp_isoformat(packet):
    """
    Get the capture time in ISO format from the packet.
    This function retrieves the frame time epoch from the packet and converts it to ISO format.
    :param packet: The packet to get the capture time from.
    :return: The capture time of the packet in ISO format.
    """
    try:

        frame_layer = get_layer(packet, "frame")

        time = frame_layer.get('frame.time_epoch')
        if time is not None:
            # Convert the time to a datetime object
            return datetime.datetime.fromtimestamp(float(time)).isoformat()
        else:
            app_logger.warning("Frame time epoch not found in packet")

    except (ValueError, TypeError):
        return None

def get_time_stamp_epoch(packet):
    """
    Get the capture time in epoch format from the packet.
    This function retrieves the frame time epoch from the packet and returns it as a float.
    :param packet: The packet to get the capture time from.
    :return: The capture time of the packet in epoch format.
    """
    try:
        frame_layer = get_layer(packet, "frame")
        time_epoch = frame_layer.get('frame.time_epoch')
        return float(time_epoch)
    except (ValueError, TypeError):
        return None

def get_ip_src(packet):
    """
    Get the source IP address from the packet.
    This function retrieves the source IP address from the IP layer of the packet.
    It checks the 'ip' layer for the 'ip.src' field and returns its value.
    :param packet: The packet to get the source IP address from.
    :return: The source IP address of the packet.
    """
    ip_layer = get_layer(packet, "ip")
    if ip_layer:
        return ip_layer.get('ip.src')
    return None

def get_ip_dst(packet):
    """
    Get the destination IP address from the packet.
    This function retrieves the destination IP address from the IP layer of the packet.
    It checks the 'ip' layer for the 'ip.dst' field and returns its value.
    :param packet: The packet to get the destination IP address from.
    :return: The destination IP address of the packet.
    """
    ip_layer = get_layer(packet, "ip")
    if ip_layer:
        return ip_layer.get('ip.dst')
    return None

def get_udp_srcport(packet):
    """
    Get the source UDP port from the packet.
    This function retrieves the source UDP port from the UDP layer of the packet.
    It checks the 'udp' layer for the 'udp.srcport' field and returns its value.
    :param packet: The packet to get the source UDP port from.
    :return: The source UDP port of the packet.
    """
    udp_layer = get_layer(packet, "udp")
    if udp_layer:
        return udp_layer.get('udp.srcport')
    return None

def get_udp_dstport(packet):
    """
    Get the destination UDP port from the packet.
    This function retrieves the destination UDP port from the UDP layer of the packet.
    It checks the 'udp' layer for the 'udp.dstport' field and returns its value.
    :param packet: The packet to get the destination UDP port from.
    :return: The destination UDP port of the packet.
    """
    udp_layer = get_layer(packet, "udp")
    if udp_layer:
        return udp_layer.get('udp.dstport')
    return None

def get_ssrc(packet):
    """
    Get the SSRC (Synchronization Source) from the RTP packet.
    This function retrieves the SSRC from the RTP layer of the packet.
    It checks the 'rtp' layer for the 'rtp.ssrc' field and returns its value.
    :param packet: The packet to get the SSRC from.
    :return: The SSRC of the RTP packet.
    """
    rtp_layer = get_layer(packet, "rtp")
    if rtp_layer:
        return rtp_layer.get('rtp.ssrc')
    return None

def get_rtp_payload(packet):
    """
    Get the RTP payload from the RTP packet.
    This function retrieves the RTP payload from the RTP layer of the packet.
    It checks the 'rtp' layer for the 'rtp.payload' field and returns its value.
    :param packet: The packet to get the RTP payload from.
    :return: The RTP payload of the packet.
    """
    rtp_layer = get_layer(packet, "rtp")
    if rtp_layer:
        return rtp_layer.get('rtp.payload')
    return None

def get_opus_frame_data(packet):
    """
    Get the Opus frame data from the RTP packet.
    This function retrieves the Opus frame data from the RTP layer of the packet.
    It checks the 'opus' layer for the 'opus.frame_data' field and returns its
    value if available.
    :param packet: The packet to get the Opus frame data from.
    :return: The Opus frame data of the packet if available, otherwise None.
    """
    rtp_layer = get_layer(packet, "opus")
    if rtp_layer:
        return rtp_layer.get('opus.frame_data')
    return None

def get_rtp_timestamp(packet):
    """
    Get the RTP timestamp from the RTP packet.
    This function retrieves the RTP timestamp from the RTP layer of the packet.
    It checks the 'rtp' layer for the 'rtp.timestamp' field and returns its value.
    :param packet: The packet to get the RTP timestamp from.
    :return: The RTP timestamp of the packet if available, otherwise None.
    """
    rtp_layer = get_layer(packet, "rtp")
    if rtp_layer:
        return int(rtp_layer.get('rtp.timestamp'))
    return None

def get_via_branches(sip):
    """
    Get the Via branches from the SIP message header tree.
    This function retrieves the Via branches from the SIP message header tree.
    It checks the 'sip.msg_hdr_tree' for the 'sip.Via_tree' and extracts the
    'sip.Via.branch' field from each Via entry.
    :param sip: The SIP message contains the header tree.
    :return: The list of Via branches as strings.
    """

    # Get the Via branches from the SIP message header tree.
    via_tree = sip.get('sip.msg_hdr_tree', {}).get('sip.Via_tree', [])

    # Ensure via_tree is a list, if not make it a list
    if isinstance(via_tree, dict):
        via_tree = [via_tree]

    # Extract the 'sip.Via.branch' from each Via entry.
    branches = []
    for via in via_tree:
        branch = via.get('sip.Via.branch')
        if branch is not None:
            branches.append(branch)
    return branches

# =========================================================
#                   Tshark processing Method
# =========================================================

def handle_duplicates(pairs):
    """
    Process a list of key-value pairs to handle duplicates.
    This function takes a list of key-value pairs and returns a dictionary.
    If a key appears multiple times, it collects all values into a list.
    If no duplicates are found, it returns a normal dictionary.
    If duplicates are found, it returns an OrderedDict with lists of values.
    :param pairs: The list of key-value pairs to process.
    :return: The processed dictionary with unique keys or lists of values for duplicates.
    """

    storage: dict[str, list] = {} # storage for unique keys
    duplicates: dict[str, list] = {} # storage for duplicate keys as lists

    for key, val in pairs:
        if key in storage:
            # Key already exists, check for duplicates
            if key not in duplicates:
                # If it's the first duplicate, create a list with the original value
                duplicates[key] = [storage[key]]
            duplicates[key].append(val)
        else:
            # Key is unique, store it in the storage dict
            storage[key] = val

    if not duplicates:
        # no duplicates found, return the original storage as a normal dict
        return storage

    else:
        # duplicates found, return an OrderedDict with lists of values
        o_dict = OrderedDict()

        # Insert all keys from storage, but replace duplicates with their lists
        for key, val in pairs:
            if key in duplicates:
                # If the key is in duplicates, use the list of values
                if key not in o_dict:
                    o_dict[key] = duplicates[key]
            else:
                # If the key is not in duplicates, use the original value
                o_dict.setdefault(key, storage[key])

        return o_dict
