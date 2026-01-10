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
5. [Config.ini](#configini)
6. [The UI](#the-ui)
5. [Usage](#usage)
7. [Known Issues](#known-issues)
8. [FAQ](#faq)
9. [License](#license)

---

## General Info
The Bachelor_VoIP_Softphone is a Python tool for the automated analysis of
VoIP phone calls (SIP/RTP). It can directly read a PCAP file (e.g. from Wireshark) or
live network traffic on a network interface. The program is splitting up in different threads to increase
the performance, and the individual sections can communicate via RabbitMQ.
The program captures and process SIP and RTP packets, reconstructs the audio streams, and performs
Voice Activity Detection (VAD) to identify voice segments. <br> 
The program saves all metadata (call ID, participants, SSRCs, voice segments) in a local SQLite database. 
A web interface for visualizing the call statistics is intended to display this collected data in 
detail and provide an overview. <br>
The program was developed as a bachelor's thesis in the Computer Science degree
at the Johannes Kepler University Linz (Upperaustria, Austria). <br>

The Program is designed to run on linux as a docker container, or on Windows as a normal program.
In the Installation section, you can find the instructions on how to install the program and the required libraries. <br>


## Project Status
The program has now been fully developed and enables the full scope described.
Various tests were carried out to verify the functionality of the program, all of which were successful.
An end-to-end test was also carried out, which confirmed the functionality of the program.<br>

Nevertheless, small bugs may occur that did not appear during development.
If any bugs occur, please report them in the issue tracker 
and I will try to fix them as soon as possible.<br>

## Prerequisites and Technologies
This program uses additional libraries and applications that are not supplied with Python. 
These must be installed separately in the respective compatible version.

- Python >= 3.13
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
- passlib = 1.7.4
- PyJWT = 2.10.1
- sse-starlette = v2.4.1


Licenses of the Library's: [Link](THIRD_PARTY_LICENSES.md)

The program also requires a running RabbitMQ server, which can be installed via Docker. <br>
A [Docker Compose File](docker-compose.yml) is provided in the repository, which <br>
can be used to build a Docker image for RabbitMQ.

The Program uses also the tshark command line tool from Wireshark to capture live network traffic. <br>
Tshark is a network protocol analyzer that can capture and display network packets in real-time.
It is used to capture SIP and RTP packets from the network interface and process them in the program.
You should have Wireshark installed on your system to use the program. <br>
If you use the Dockerfile to create a Docker image, the tshark command line tool will be installed automatically with the Dockerfile. <br>
Important: The tshark command line tool us not integrated in the program. The program us calling the 
tshark command line tool via a subprocess, so you need to have tshark installed on your system. <br>
You should download Wireshark from the [official website](https://www.wireshark.org) separately to use the program. <br>


## Installation Windows

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
pip install passlib
pip install PyJWT
pip install sse-starlette
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
The user data and password must be inserted in the `config.ini` file. 
Also, the server IP and port must be specified, <br>
so that the program can connect to the RabbitMQ server. <br>



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

## Installation Linux

### Clone the repository
To clone the repository, you can use the following command in your terminal or command prompt:
```bash
git clone https://github.com/lightningstorch/Bachelor_VoIP_Softphone.git
```
To clone the Repository, you need a Github account. If you do not have one, you can create <br>
one for free at [github.com](https://github.com/)

### Install Docker
The program for linux is designed to run in a Docker container, so you need to have Docker installed on your system. <br>
You can install Docker by following the instructions on the [official website](https://www.docker.com/products/docker-desktop). <br>

### Install the environment
The Dockerfile and the docker-compose.yml provide all necessary scripts to install all requirements 
and make adjustments to the Docker container.

Therefore, the following command only needs to be executed in the docker-compose.yml folder on the command line:
```bash
docker-compose up --build
```
Then the container is built and started and can be accessed directly with the UI 
(adjust server API URL in the UI .env file if necessary!)

## Config.ini
The config.ini file is used to store the configuration settings for the program. <br>
You can find there some specific settings that need to be adjusted before running the program. <br>
The ServerIP of the SIP / RTP Server must be specified, to identify the Server in the Network protocols. <br>
Also you need to specify the Network Interface, which is used to capture the packets (windows and linux separately). 
(for example: Ethernet, eps0, ...) <br>

### The UI
The first version of the UI is now available and can be used to visualize the data processed by the program. <br>
It is a web-based interface that allows you to view the call statistics, participants, and voice segments. <br>
You can also process live network traffic or PCAP files and visualize the data in real-time. <br>

The Repository: [UI-Project-Link](https://github.com/lightningstorch/Bachelor_VoIP_UI)

## Usage
The program can be used to process SIP and RTP packets from a PCAP file or live network traffic.
To use the program, you need the UI project, which is a web-based interface that allows you to visualize 
the data processed by the program and also to process live network traffic or PCAP files.

For Windows user only:
```text
Program can be started with the command `python main.py` or in the IDE, but the 
Docker container RabbitMQ must be running so that the messages can be processed.
It is important that the required libraries are installed and recognized.
```

The output currently (as of 21.07.2025) in the console looks as follows:
(Some important parts of the output are sent to the UI via SSE, so they are also displayed in the UI.)
```text
Starting capture provider thread in mode: live
Starting packet processor thread
🟢 [SSE] New client connected
Starting capture provider thread in mode: file
Starting packet processor thread
Aggregator: New call is temporarily saved: 'HfjUoRN6VP'
ACK
Aggregator Buffer: CallInfo(caller='Linphone2', start_time=datetime.datetime(2025, 6, 18, 16, 17, 23, 473656), end_time=None, participants=[ParticipantInfo(user='Linphone2', ip_address='192.168.0.55', media_port=44411, mime_type='opus', server_ip='192.168.0.63', server_port=30264, ssrc=None), ParticipantInfo(user='linphpne1', ip_address='192.168.0.52', media_port=53184, mime_type='opus', server_ip='192.168.0.63', server_port=30244, ssrc=None)], ack_received=True, stored=False)
Call ID 'HfjUoRN6VP' has been stored in db
SSRC '0xe39fcb21' has been updated for call ID 'HfjUoRN6VP' in db
SSRC '0xd1a843d0' has been updated for call ID 'HfjUoRN6VP' in db
Speech intervals for SSRC '0xd1a843d0': [(1.36, 22.56)]
Speech intervals for SSRC '0xe39fcb21': [(30.46, 40.24)]
Speech intervals for SSRC '0xe39fcb21': [(50.48, 56.78)]
BYE
200: SIP/2.0 200 Ok BYE
[FLUSH] Final speech interval for SSRC '0xd1a843d0': [(49.92, 65.92)]
CallInfo(caller='Linphone2', start_time=datetime.datetime(2025, 6, 18, 16, 17, 23, 473656), end_time=datetime.datetime(2025, 6, 18, 16, 18, 30, 381003), participants=[ParticipantInfo(user='Linphone2', ip_address='192.168.0.55', media_port=44411, mime_type='opus', server_ip='192.168.0.63', server_port=30264, ssrc='0xe39fcb21'), ParticipantInfo(user='linphpne1', ip_address='192.168.0.52', media_port=53184, mime_type='opus', server_ip='192.168.0.63', server_port=30244, ssrc='0xd1a843d0')], ack_received=True, stored=True)
Call ID 'HfjUoRN6VP' has been updated in db
Aggregator: Call ID 'HfjUoRN6VP' has been finished and stored in db
```

The `app.db` database is created automatically if it does not exist and stores 
the most necessary data in the database to assign the RTP and SIP packets. The 
call times will be included in the next version.

### Info: 
The live capture provider thread is started by default, and cannot be stopped, becuase of an issue with the Pyshark package. <br>
The API is switching the mode of the ProgramStateManager and does not start a new live capture provider thread.
But the live capture provider thread from the program start is still running in the background. <br>


## Known Issues
Some issues are known and will be fixed in the future.

| Issue                           | Description                                                                                                                                                                                                                                                                                                                                                | Status                   |
|---------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|--------------------------|
| admin access                    | Currently, the admin password is stored in plain text in the config.ini file, which can lead to security problems if the password is not customized via UI.                                                                                                                                                                                                | in the next version      |
| Tshark (Pyshark package)        | The package Pyshark uses Tshark in the background and creates a process at sniff_continiously, which is needed to intercept live traffic, which is very difficult to terminate. Therefore, the change_mode api change only the ProgramStateManager and does not start a new live capture thread. This should be updated and changed to handle this besser. | in the next version      |

## FAQ
### Why is the program so slow?
The program is designed to process VoIP calls in a captured PCAP file or live network traffic.
To process the packets, the program needs to analyze each packet and reconstruct the audio streams.
This can take some time, especially if the PCAP file is large or the network traffic is high.
For the best performance, it is recommended to use a powerful computer with a fast CPU and enough RAM. <br>

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

