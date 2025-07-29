FROM python:3.13-slim

# (optional) damit apt‑get nicht nach Bestätigungen fragt
ENV DEBIAN_FRONTEND=noninteractive

# install the nessessary packages for Wireshark and Pyshark
RUN apt-get update \
  && apt-get install -y --no-install-recommends \
     build-essential \
     netcat-openbsd \
     tshark \
     wireshark-common \
     libpcap-dev \
     libglib2.0-dev \
     wireshark \
     tcpdump \
  && rm -rf /var/lib/apt/lists/*

# set the wireshark to root user
RUN groupadd wireshark && \
    usermod -a -G wireshark root

# create Wireshark configuration directory and set permissions
RUN mkdir -p /root/.config/wireshark && \
    echo "gui.geometry_main_x: 0" > /root/.config/wireshark/recent && \
    echo "gui.geometry_main_y: 0" >> /root/.config/wireshark/recent

# set wireshark preferences for better protocol detection
# (nessessary to detect all rtp streams)
RUN mkdir -p /etc/wireshark && \
    echo "# Enable all dissectors" > /etc/wireshark/preferences && \
    echo "rtp.heuristic_rtp: TRUE" >> /etc/wireshark/preferences && \
    echo "rtp.show_setup_info: TRUE" >> /etc/wireshark/preferences

WORKDIR /app

COPY requirements.txt .
RUN pip install --upgrade pip setuptools wheel \
 && pip install --no-cache-dir -r requirements.txt

# Copy the wait-for-rabbit script to the container
# nessesary to wait for RabbitMQ to be ready before starting the application
COPY wait-for-rabbit.sh /usr/local/bin/wait-for-rabbit.sh
RUN chmod +x /usr/local/bin/wait-for-rabbit.sh

# in the dev mode it isn't nessesary to copy the source code into the container
# because we mount the source code into the container
#COPY . .

# set environment variables for wireshark for better perfoemance
ENV PYSHARK_CONFIG_DIR=/etc/wireshark
ENV WIRESHARK_CONFIG_DIR=/etc/wireshark

ENTRYPOINT ["/usr/local/bin/wait-for-rabbit.sh"]