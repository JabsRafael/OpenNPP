# Base image
FROM ubuntu:20.04

# Set environment variable to non-interactive
ENV DEBIAN_FRONTEND=noninteractive

# Install necessary packages
RUN apt-get update && apt-get install -y \
    git \
    gcc \
    g++ \
    make \
    libmodbus-dev \
    python3 \
    python3-pip \
    python3-venv \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* || true

# Retry mechanism
RUN apt-get update --fix-missing && apt-get install -y \
    git \
    gcc \
    g++ \
    make \
    libmodbus-dev \
    python3 \
    python3-pip \
    python3-venv \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Clone OpenPLC repository
RUN git clone https://github.com/JabsRafael/OpenPLC_v3.git /opt/OpenPLC

# Installing Nano
RUN apt-get update && apt-get install -y nano

# Setting nano as default editor
ENV EDITOR=nano

# Change directory and install OpenPLC
WORKDIR /opt/OpenPLC
RUN ./install.sh docker

# Create a virtual environment and install Python dependencies
RUN python3 -m venv /opt/OpenPLC/.venv && \
    /opt/OpenPLC/.venv/bin/pip install --upgrade pip


# Set the working directory
WORKDIR /opt/OpenPLC/webserver

# Copy the Python Slave Files to the container

RUN mkdir /opt/OpenPLC/webserver/Slave_Test
COPY ./Slave_Test /opt/OpenPLC/webserver/Slave_Test

# Command to run OpenPLC
CMD ["/opt/OpenPLC/.venv/bin/python3", "webserver.py"]

RUN /opt/OpenPLC/.venv/bin/python3 /opt/OpenPLC/webserver/Slave_Test/Slave01.py &