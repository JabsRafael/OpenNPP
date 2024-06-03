#!/bin/bash

# Start the webserver
/opt/OpenPLC/.venv/bin/python3 /opt/OpenPLC/webserver/webserver.py &

# Start the Slave01 script
/opt/OpenPLC/.venv/bin/python3 /opt/OpenPLC/webserver/Slave_Test/Slave01.py &

# Keep the script running (to keep the Docker container alive)
wait
