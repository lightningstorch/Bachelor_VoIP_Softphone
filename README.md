# Project Name
*A Python-based analysis tool for VoIP calls (SIP/RTP) that either records live traffic
or uses PCAP dumps to reconstruct audio, recognize voice segments 
and generate call statistics.*

---

## Table of Content
1. [General Info](#general-info)
2. [Project Status](#project-status)
3. [Prerequisites and Technologies](#prerequisites-and-technologies)
4. [Installation](#installation)
5. [Usage](#usage)
7. [Known Issues](#known-issues)
8. [FAQ](#faq)
9. [License](#license)

---

## General Info
The Bachelor_VoIP_Softphone is a Python tool for the automated analysis of <br>
VoIP phone calls (SIP/RTP). It can directly read in a PCAP file (e.g. from Wireshark) or <br>
live network traffic on a network interface. Packets are processed in separate threads via RabbitMQ: <br>
SIP signaling is evaluated, RTP audio streams are reconstructed and broken down into voice intervals<br>
using Voice Activity Detection (VAD). The program saves all metadata (call ID, participants, SSRCs, <br>
voice segments) in a local SQLite database. A web interface for visualizing the call statistics <br>
is intended to display this collected data in detail and provide an overview. <br>
The program was developed as a bachelor's thesis in the Computer Science degree <br>
program at the Johannes Kepler University Linz. <br>


## Project Status
| Technology         | Description                                                                                                 | Status              |
|--------------------|-------------------------------------------------------------------------------------------------------------|---------------------|
| Audio processing   | Processing of RTP packets and recognition of speech segments <br> in the audio (currently without music on hold) | in progress         |
| UI (Webbased / PC) | Development of a UI for the visual representation of <br> the most necessary data from the program          | planed in 1-2 Weeks |
| Testing            |  Development of tests to prove the function       | in progress         |


## Prerequisites and Technologies
This program uses additional libraries and applications that are not supplied with Python. 
These must be installed separately in the respective compatible version.

- Python >= 3.13
- pyshark = 0.6
- cachetools = 5.5.2
- SQLAlchemy = 2.0.40
- aio-pika = 9.5.5
- pydantic = 2.11.4
- av = 14.4.0
- webrtcvad = 2.0.10
- numpy = 2.2.6
- scipy = 1.15.3
- uvicorn = 0.35.0
- fastapi = 0.115.14
- python-multipart = 0.0.20


Licenses of the Library's: [Link](THIRD_PARTY_LICENSES.md)

The program also requires a running RabbitMQ server, which can be installed via Docker. <br>
A [Docker Compose File](rabbitmq-docker/docker-compose.yml) is provided in the repository, which <br>
can be used to build a Docker image for RabbitMQ.


## Installation

### Clone the repository
To clone the repository, you can use the following command in your terminal or command prompt:
```bash
git clone https://github.com/lightningstorch/Bachelor_VoIP_Softphone.git
```
To clone the Repository, you need a Github account. If you do not have one, you can create <br>
one for free at [github.com](https://github.com/)

### Install the required libraries
```bash
pip install -r requirements.txt
```
or if an error occurs, you can install the libraries individually:
```bash
pip install pyshark
pip install cachetools
pip install SQLAlchemy
pip install aio-pika
pip install pydantic
pip install scapy
pip install av
pip install webrtcvad
pip install numpy
pip install uvicorn
pip install fastapi
pip install python-multipart
```

### Install the RabbitMQ server
To install RabbitMQ, you can use Docker. Make sure you have Docker installed on your system. <br>

1. Install Docker Desktop or Terminal from the [official website](https://www.docker.com/products/docker-desktop).
2. After installation, open Docker Desktop and ensure it is running.
3. Open a terminal or command prompt and navigate to the directory where you want to store the RabbitMQ Docker files.
4. Run the following command to start the RabbitMQ server:
```bash
docker-compose up -d
```

If it is running, you can access the Rabbit MQ management interface by opening your web browser and <br>
navigating to `http://localhost:15672`. <br>
The default username and password are both `guest`. <br>

You can use the default User or crate a new one for your Program. <br>
The user data and password must be inserted in the config.ini file. 
Also, the server IP and port must be specified, <br>
so that the program can connect to the RabbitMQ server. <br>

### Config.ini
The config.ini file is used to store the configuration settings for the program. <br>
You can find there some specific settings that need to be adjusted before running the program. <br>
The ServerIP of the SIP / RTP Server must be specified, to identify the Server in the Network protocols. <br>
Also you need to specify the Network Interface, which is used to capture the packets. (for example: Ethernet, eps0, ...) <br>


### Running the Program
The Server program is designed to run in a multi-threaded environment, where one thread captures the packets <br>
and another processes them, and every call is processed in a separate call context thread. <br>
To run the program, you can use the following command in your terminal or command prompt:
```bash
python main.py
```
or
```bash
python3 main.py
```

### The UI
The UI is currently in development and will be available in the view version of the program. <br>
It will be accessible via a web browser or program on the pc and will provide a visual representation <br>
of the data processed by the program. <br>

## Usage
The program needs a recorded or live network traffic, which ideally 
was recorded with Wireshark. The path to the file must be inserted in the config.ini file (later via the UI).
You must also specify whether it is an absolute or relative path so that the path can be resolved correctly. 
For test purposes, an example of a recorded file is provided under the folder data, which gives 
the desired output.

Program can be started with the command `python main.py` or in the IDE, but the 
Docker container RabbitMQ must be running so that the messages can be processed.
It is important that the required libraries are installed and recognized.

The output currently (as of 05.06.2025) in the console looks as follows:
(The outputs are currently only intended for debugging and testing purposes and will be removed in the final 
version)
```text
Starting packet monitor thread
Starting packet processor thread
Aggregator: New call is temporarily saved: 'duLG15PLM6'
200: SIP/2.0 200 Ok INVITE
ACK
Aggregator: Buffer: CallInfo(start_time=datetime.datetime(2025, 6, 3, 13, 25, 20, 780962), end_time=None, participants=[ParticipantInfo(user='linphone2', ip_address='192.168.0.56', media_port=37923, mime_type='opus', server_ip='192.168.0.63', server_port=30194, ssrc=None), ParticipantInfo(user='linphpne1', ip_address=None, media_port=None, mime_type=None, server_ip='192.168.0.63', server_port=30204, ssrc=None)])
Call ID 'duLG15PLM6' already exists in db
SSRC '0x264b147f' has been updated for call ID 'duLG15PLM6' in db
SSRC '0x65bc380a' has been updated for call ID 'duLG15PLM6' in db
Speech intervals for SSRC 0x264b147f: [(1.4, 15.12)]
Speech intervals for SSRC 0x264b147f: [(16.54, 22.6)]
Speech intervals for SSRC 0x264b147f: [(23.74, 31.56), (32.56, 37.4)]
Speech intervals for SSRC 0x65bc380a: [(50.16, 70.6)]
Speech intervals for SSRC 0x65bc380a: [(95.22, 98.42)]
Speech intervals for SSRC 0x264b147f: [(80.4, 100.48)]
Speech intervals for SSRC 0x65bc380a: [(106.8, 107.66)]
BYE
200: SIP/2.0 200 Ok BYE
[FLUSH] Final speech interval for SSRC 0x65bc380a: (109.86, 119.94)
CallInfo(start_time=datetime.datetime(2025, 6, 3, 13, 25, 20, 780962), end_time=datetime.datetime(2025, 6, 3, 13, 27, 21, 260515), participants=[ParticipantInfo(user='linphone2', ip_address='192.168.0.56', media_port=37923, mime_type='opus', server_ip='192.168.0.63', server_port=30194, ssrc='0x264b147f'), ParticipantInfo(user='linphpne1', ip_address=None, media_port=None, mime_type=None, server_ip='192.168.0.63', server_port=30204, ssrc='0x65bc380a')])
Call ID 'duLG15PLM6' has been updated in db
Aggregator: Call ID 'duLG15PLM6' has been finished and stored in db
```

The `app.db` database is created automatically if it does not exist and stores 
the most necessary data in the database to assign the RTP and SIP packets. The 
call times will be included in the next version.


## Known Issues
Currently in preparation

| Issue               | Description                                                                 | Status                 |
|---------------------|-----------------------------------------------------------------------------|------------------------|
| Code Duplication    | the file packet_processor.py contains some code duplication                 | in progress            |
| Improve performance | Laptop hardware must have enough power for fast execution (min. 4 Core CPU) | planed for future Work |

## FAQ
### Why is the program so slow?
The program is currently in development, and the performance will be improved in the next versions. <br>
And the program processes a large number of packets, which can lead to high CPU utilization. <br>

### Why does the program only work with PCAP file or PCAPNG?
The program is designed to process SIP and RTP packets, which are typically captured in PCAP or PCAPNG files. <br>
It is also the most common format for network traffic (Wireshark use this format also). <br>

### Why does the program not work with other network protocols?
The program is specifically designed to process SIP and RTP packets, which are used in VoIP calls. <br>
Other network protocols may not be supported, but the program can be extended to support other protocols in the future. <br>

### Why does the program not work with other audio codecs?
The program currently supports the Opus codec, which is commonly used in VoIP calls. <br>
Other audio codecs may not be supported, but the program can be extended to support other codecs in the future. <br>

### Why does the program not work with a wireless network interfaces?
In normal ‘Managed Mode’, your WLAN adapter only receives those frames that are intended for your own <br>
MAC address (or broadcast/multicast); to really listen to all radio packets, <br>
the card must be switched to ‘Monitor Mode’ (passive sniffing) and operated on the correct channel. <br>
Many WLAN cards do not support this mode.

### Why does the program not work with encrypted SIP/RTP?
The program is designed to process unencrypted SIP and RTP packets because the analysis of the audio <br>
requires access to the raw audio data and this is not possible with encrypted packets. <br>
It will be possible, when the encryption keys are available, to decrypt the packets and process them. <br>
But this is not implemented yet. <br>

## License
This program is developed to use it as a closed Source. It could be that it will be open source in the future, but <br> 
currently it is not planned. <br>

