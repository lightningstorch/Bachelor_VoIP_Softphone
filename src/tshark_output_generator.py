import os
import subprocess
import json
from pathlib import Path

from utils.packet_parsing import handle_duplicates


def tshark_output():
    path = os.path.join(Path(__file__).parent.parent, "tests", "data", "tshark_output_generator_files")

    pcap_file = os.path.join(path, "sip_packets.pcapng")
    tshark_cmd = [
        'tshark',
        '-r', pcap_file,
        '-T', 'json',
        '-Y', 'sip', # change the filter for sip and rtp as needed
    ]

    try:
        # the output from tshark
        output = subprocess.check_output(tshark_cmd, text=True)

        print("=== ROHER JSON OUTPUT ===")
        print(output)

        # load the json output and convert it using smart_pairs to handle duplicates
        # loaded_data = json.loads(output, object_pairs_hook=handle_duplicates)
        # print(loaded_data)

    except subprocess.CalledProcessError as e:
        print(f"Error executing tshark command: {e}")
        print(f"Command output: {e.output}")

if __name__ == "__main__":
    tshark_output()
