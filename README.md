# VoIP call analyzer (SIP/RTP)

A Python tool that analyzes VoIP calls on the network. It reads SIP and RTP packets either live from a network interface or from a PCAP/PCAPNG file, rebuilds the audio of each call, finds the parts where someone is speaking and stores the call data in SQLite. A REST API with Server-Sent Events delivers the results to the [web UI](https://github.com/lightningstorch/Bachelor_VoIP_UI).

I built it for my bachelor's thesis in Computer Science at Johannes Kepler University Linz (2025).

## How it works

1. **Capture.** `tshark` runs as a subprocess with the display filter `sip or rtp`, either on a live interface or on a capture file.
2. **Parsing.** The packet processor reads the SIP dialog (INVITE, ACK, BYE, response codes) and assigns RTP streams to calls by SSRC, IP address and port.
3. **One thread per call.** Every call gets its own call context that buffers its RTP packets.
4. **Audio analysis.** The Opus audio is decoded with PyAV, cleaned with a band-pass filter (300 to 3400 Hz by default) and noise reduction, and passed through WebRTC voice activity detection. The result is a list of speech intervals per participant.
5. **Messaging and storage.** The parts exchange events over RabbitMQ (aio-pika). An aggregator collects call start, participants, SSRCs and speech intervals and writes them to SQLite with SQLAlchemy.
6. **API.** FastAPI serves the call history and call details, lets the UI switch between live and file mode, upload captures and manage users (JWT login). Log messages are streamed to the UI with Server-Sent Events.

## Tech stack

Python 3.13, tshark, RabbitMQ (aio-pika), FastAPI, Uvicorn, sse-starlette, SQLAlchemy with SQLite, pydantic, PyAV, webrtcvad, NumPy, SciPy, PyJWT and passlib. Docker and Docker Compose for the Linux setup, pytest for the tests. The licenses of all libraries are listed in [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md).

## Requirements

- Python 3.13
- tshark from [Wireshark](https://www.wireshark.org). The program calls it as a subprocess, so it has to be installed and on the `PATH`. The Docker image installs it automatically.
- A RabbitMQ server. `docker-compose.yml` starts one.

## Configuration

The settings are in [`src/config/config.ini`](src/config/config.ini). A `config.ini` in the current working directory takes precedence over this file, so you can keep your own settings outside the repository.

The most important values:

| Section | Key | Meaning |
|---|---|---|
| `network` | `server_ip` | IP address of the SIP/RTP server, used to tell server and clients apart |
| `network` | `interface_linux`, `interface_windows` | network interface for live capture, e.g. `eth0` or `Ethernet` |
| `captured_file` | `path`, `file_path` | capture file for file mode, `path` is `relative` or `absolute` |
| `rabbitmq` | `user`, `password`, `host_*`, `port` | connection to RabbitMQ |
| `audio_processing` | `vad_mode`, `gap_threshold`, `bandpass_*`, ... | parameters of the audio analysis |

Secrets are not stored in the repository:

- `SECRET_KEY` signs the JWT tokens. If it is neither set as an environment variable nor in `config.ini`, the program generates a random key on every start. Users then have to log in again after a restart.
- `ADMIN_USERNAME` and `ADMIN_PASSWORD` define the admin user that is created on the first start. If no password is set, the program generates one and writes it to the log once. Change it in the UI after the first login.
- `DATABASE_CONNECTION` overrides the SQLite connection string.

## Running on Linux (Docker)

```bash
git clone https://github.com/lightningstorch/Bachelor_VoIP_Softphone.git
cd Bachelor_VoIP_Softphone
docker compose up --build
```

Compose starts RabbitMQ and the analyzer. The container needs `NET_ADMIN` and `NET_RAW` to capture traffic. The API listens on port 8000, the RabbitMQ management interface on `http://localhost:15672`. Compose passes `SECRET_KEY`, `ADMIN_USERNAME` and `ADMIN_PASSWORD` from your shell into the container, e.g. `SECRET_KEY=$(openssl rand -hex 32) docker compose up --build`.

## Running on Windows

1. Install Wireshark (includes tshark) and Docker Desktop.
2. Start RabbitMQ: `docker compose up -d rabbitmq`
3. Install the Python packages and start the program:

```bash
git clone https://github.com/lightningstorch/Bachelor_VoIP_Softphone.git
cd Bachelor_VoIP_Softphone
pip install -r requirements.txt
python src/main.py
```

The default RabbitMQ user is `guest` with password `guest`. If you create your own user in the management interface, enter it in `config.ini`.

## Usage

The program starts in live mode on the configured interface. The [UI](https://github.com/lightningstorch/Bachelor_VoIP_UI) can switch to file mode, upload PCAP or PCAPNG files and show the history and details of each call.

A shortened example of the console output for one call from a capture file:

```text
Starting capture provider thread in mode: file
Aggregator: New call is temporarily saved: 'HfjUoRN6VP'
Call ID 'HfjUoRN6VP' has been stored in db
SSRC '0xe39fcb21' has been updated for call ID 'HfjUoRN6VP' in db
SSRC '0xd1a843d0' has been updated for call ID 'HfjUoRN6VP' in db
Speech intervals for SSRC '0xd1a843d0': [(1.36, 22.56)]
Speech intervals for SSRC '0xe39fcb21': [(30.46, 40.24)]
BYE
[FLUSH] Final speech interval for SSRC '0xd1a843d0': [(49.92, 65.92)]
Aggregator: Call ID 'HfjUoRN6VP' has been finished and stored in db
```

The SQLite database `app.db` is created automatically on the first start.

## Tests

```bash
pip install -r requirements.txt
pytest
```

`tests/test_api.py` and `tests/test_end_to_end.py` need a running RabbitMQ. The end-to-end tests and the capture provider integration test also need sample captures in `tests/data/`. Without the sample file the capture provider test is skipped.

## Known limitations

- Only unencrypted SIP and RTP can be analyzed. SRTP would need the keys to decrypt the audio, which is not implemented.
- Speech detection works on Opus audio. Other codecs are not supported yet.
- Live capture on Wi-Fi only sees the frames addressed to your own device, unless the adapter supports monitor mode. Use a wired interface or a mirror port.
- The live capture thread that starts with the program keeps running in the background. Switching modes through the API changes the state of the `ProgramStateManager` instead of starting a new live capture.
- Large captures and busy networks take a while, because every packet is parsed and every call is decoded.

## License

Licensed under the GPLv3, see [LICENSE.txt](LICENSE.txt).
