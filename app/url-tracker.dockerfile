# Use Python 3.11 slim image as base
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    vim \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# for running the image without mounted volumes
# RUN mkdir -p /app/logs
# RUN mkdir -p /app/data
RUN mkdir -p /app/src

# Switch to non-root user
USER 1002:1002


# Copy application code
COPY src/main.py src/main.py
COPY src/security.py src/security.py
COPY src/pages/ src/pages/

# Expose port 8000
EXPOSE 8000

# Command to run the application
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload", "--reload-include", "*.yml"]
