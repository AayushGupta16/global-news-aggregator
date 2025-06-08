# Dockerfile

# Use the official Microsoft Playwright image for Python 3.12
# This base image includes Python and all necessary system dependencies for browsers.
FROM mcr.microsoft.com/playwright/python:v1.52.0-jammy

# --- VNC and GUI Setup ---
# Install a lightweight window manager, VNC server, and other tools
RUN apt-get update && apt-get install -y \
    fluxbox \
    xterm \
    tigervnc-standalone-server \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Set the working directory inside the container
WORKDIR /app

# Copy the requirements file first
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your application code into the container
COPY . .

# --- Port Exposure ---
# Expose the FastAPI port
EXPOSE 8000
# Expose the VNC port
EXPOSE 5901

# The new command to run your application using the startup script
CMD ["/app/start.sh"]