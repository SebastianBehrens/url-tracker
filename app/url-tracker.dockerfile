# Use Python 3.13 slim image as base
FROM python:3.13-slim


# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    vim \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# change ownership of the app directory to the non-root user
RUN chown -R 1002:1002 /app

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Switch to non-root user
USER 1002:1002


# for running the image without mounted volumes
# RUN mkdir -p /app/logs
# RUN mkdir -p /app/data
RUN mkdir -p /app/src

# Copy application code
COPY src/main.py src/main.py
COPY src/security.py src/security.py
COPY src/pages/ src/pages/

# Expose port 8000
EXPOSE 8000

CMD WATCHFILES_FORCE_POLLING=1 python -m uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload --reload-include config.yml --use-colors