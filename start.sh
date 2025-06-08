#!/bin/bash

# start.sh

# Set the display environment variable for GUI applications
export DISPLAY=:1

# Start a lightweight window manager in the background
fluxbox &

# Start the VNC server in the background
# -geometry: sets the desktop resolution
# -depth: sets the color depth
# -rfbport: sets the VNC port
# -localhost no: allows connections from outside the container
# -xstartup: specifies the window manager to start
echo "Starting VNC server on port 5901..."
vncserver :1 -geometry 1920x1080 -depth 24 -rfbport 5901 -localhost no -xstartup /usr/bin/fluxbox

# Start the FastAPI application in the foreground
# This becomes the main process of the container
echo "Starting FastAPI application..."
exec uvicorn main:app --host 0.0.0.0 --port 8000