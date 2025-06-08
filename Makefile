# Makefile for the Multi-Country Scraper Project

# --- Variables ---
IMAGE_NAME := multi-country-scraper
CONTAINER_NAME := scraper-service
PORT_MAPPING := 8000:8000

# --- Phony Targets ---
.PHONY: all help build run stop logs shell debug requirements clean

# --- Recipes ---

# The default target. Run when you just type 'make'.
# Automates the entire stop, build, run, and log-viewing cycle.
all: stop build run

# Displays a helpful message about the available commands.
help:
	@echo "----------------------------------------------------"
	@echo " Makefile for the Multi-Country Scraper Project   "
	@echo "----------------------------------------------------"
	@echo "Usage:"
	@echo "  make              - Stop, build, run, and view logs for the app (default action)."
	@echo "  make debug          - Run the app in the foreground to see startup errors."
	@echo ""
	@echo "Individual commands:"
	@echo "  make build          - Build the Docker image"
	@echo "  make run            - Run the Docker container in the background"
	@echo "  make stop           - Stop and remove the running container"
	@echo "  make logs           - View the logs from the running container"
	@echo "  make shell          - Access a shell inside the running container for debugging"
	@echo "  make clean          - Remove stopped containers and dangling images"
	@echo "  make requirements   - Generate a requirements.txt file from a virtual environment"
	@echo ""

# Stops and removes the old container to prevent "name in use" errors.
# The '-' prefix tells make to ignore errors (e.g., if the container doesn't exist).
stop:
	@echo "--> Stopping and removing old container..."
	-docker stop $(CONTAINER_NAME)
	-docker rm $(CONTAINER_NAME)

# Build the Docker image using the Dockerfile in the current directory.
build:
	@echo "--> Building Docker image: $(IMAGE_NAME)..."
	docker build -t $(IMAGE_NAME) .

# Run the Docker container in detached mode (-d) so it runs in the background.
# --rm automatically removes the container when it is stopped.
run:
	@echo "--> Running Docker container '$(CONTAINER_NAME)'..."
	docker run -d -p $(PORT_MAPPING) --name $(CONTAINER_NAME) $(IMAGE_NAME)

# Follow the logs (-f) of the running container. Press Ctrl+C to exit.
logs:
	@echo "--> Following logs. Press Ctrl+C to stop viewing."
	# Add a small delay to give the container time to start up.
	@sleep 2
	docker logs -f $(CONTAINER_NAME)

# --- DEBUGGING TARGET ---
# Runs the full stop -> build -> run cycle, but runs the container in the foreground
# so you can see the startup logs and any errors immediately.
debug: stop build
	@echo "--> Running container in DEBUG mode (foreground)..."
	# We run with -it (interactive) and without -d (detached) or --rm
	docker run -it -p $(PORT_MAPPING) --name $(CONTAINER_NAME) $(IMAGE_NAME)

# Get an interactive shell inside the running container.
shell: stop build
	@echo "Accessing shell in container '$(CONTAINER_NAME)'..."
	# Run a temporary container and get a shell to inspect files
	docker run -it --rm --entrypoint /bin/bash $(IMAGE_NAME)

# ... (requirements and clean targets remain the same) ...
requirements:
	@echo "Generating requirements.txt from current environment..."
	pip freeze > requirements.txt
	@echo "requirements.txt has been updated."
	
clean:
	@echo "Cleaning up stopped containers and dangling images..."
	docker container prune -f
	docker image prune -f
	@echo "Cleanup complete."
	
debug-vnc: stop build
	@echo "--> Running container in VNC DEBUG mode (foreground)..."
	@echo "--> Connect VNC client to localhost:5901"
	# We run with -it (interactive), without -d or --rm, and map the VNC port
	docker run -it -p $(PORT_MAPPING) -p 5901:5901 --name $(CONTAINER_NAME) $(IMAGE_NAME)