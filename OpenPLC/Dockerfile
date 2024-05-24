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
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Clone OpenPLC repository
RUN git clone https://github.com/thiagoralves/OpenPLC_v3.git /opt/OpenPLC

# Installing Nano
RUN apt-get update && apt-get install -y nano

# Setting nano as default editor
ENV EDITOR=nano

# Change directory and install OpenPLC
WORKDIR /opt/OpenPLC
RUN ./install.sh docker

# Expose the port OpenPLC runs on
EXPOSE 8080

# Set the working directory
WORKDIR /opt/OpenPLC/webserver

# Command to run OpenPLC
