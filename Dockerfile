# Dockerfile

# Use a standard Python image. bookworm is based on Debian 12.
FROM python:3.12-bookworm

# 1. Install OS-level dependencies first (your VNC tools)
RUN apt-get update && apt-get install -y \
    fluxbox \
    xterm \
    tigervnc-standalone-server \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Set the working directory inside the container
WORKDIR /app

# Copy the requirements file first
COPY requirements.txt .

# 2. Install your Python packages from requirements.txt
# This command will install 'browser-use', which in turn installs the 'playwright' Python package.
RUN pip install --no-cache-dir -r requirements.txt

# 3. NOW that the 'playwright' Python package is installed, you can use its command-line tool
# to install the browser binaries and their MANY system dependencies.
RUN playwright install --with-deps chromium

# Copy the rest of your application code into the container
COPY . .

# --- Port Exposure ---
# Expose the FastAPI port
EXPOSE 8000
# Expose the VNC port
EXPOSE 5901

# The new command to run your application using the startup script
CMD ["/app/start.sh"]