# Use a lightweight Python 3.10 image
FROM python:3.10-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    # UV configuration
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# Install system dependencies for OpenCV, WebRTC and UV
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install UV
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set working directory
WORKDIR /app

# Copy dependency files first for better caching
COPY pyproject.toml .
# No uv.lock is present yet in the root, it might be generated during sync
# COPY uv.lock . 

# Install dependencies using UV
# We use --system to install into the system site-packages of the container
RUN uv sync --frozen || uv sync

# Copy the rest of the application code
COPY . .

# Expose the server port
EXPOSE 8000

# Script to run the application
# We use 'uv run' to ensure dependencies are correctly loaded
CMD ["uv", "run", "python", "app/server.py"]
