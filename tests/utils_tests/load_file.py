import json
import os
from pathlib import Path

from utils.packet_parsing import handle_duplicates


def get_sip_sample_data(file_name: str):
    """Load sample SIP data from a JSON file based on the OS platform."""
    path = os.path.join(Path(__file__).parent.parent, "data", "output_capture", "json_files")
    path = os.path.join(path, f"{file_name}.json")

    with open(path, 'r') as file:
        data = json.load(file, object_pairs_hook=handle_duplicates)

    return data


def get_rtp_sample_data():
    """Load sample RTP data from a JSON file based on the OS platform."""
    path = os.path.join(Path(__file__).parent.parent, "data", "output_capture", "json_files")
    path = os.path.join(path, "rtp.json")

    with open(path, 'r') as file:
        data = json.load(file, object_pairs_hook=handle_duplicates)

    return data