# Dockerfile for chatbot-websearch
# Uses a small official Python image and runs uvicorn to serve the FastAPI app
FROM python:3.10-slim

# Install system deps for building wheels (if any). Keep image small.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy only requirements first to leverage Docker layer caching
COPY requirements.txt ./
# Install Python dependencies (gunicorn is provided via requirements.txt)
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . /app

# Use an unprivileged port; Render and docker-compose will map ports as needed
EXPOSE 8000

# Default command runs the FastAPI app with gunicorn using uvicorn workers
# Adjust --workers to match available CPU/memory for production
CMD ["gunicorn", "websearch:app", "-k", "uvicorn.workers.UvicornWorker", "-b", "0.0.0.0:8000", "--workers", "2", "--threads", "4", "--log-level", "info"]
