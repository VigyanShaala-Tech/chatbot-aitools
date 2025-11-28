# Dockerfile for chatbot-websearch
# Uses Python 3.13 and uv for fast, reliable dependency installation
FROM python:3.13-slim

# Install uv - the fast Python package installer
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Copy only requirements first to leverage Docker layer caching
COPY requirements.txt ./

# Install Python dependencies using uv (much faster than pip)
RUN uv pip install --system --no-cache -r requirements.txt

# Copy application
COPY . /app

# Use an unprivileged port; Render and docker-compose will map ports as needed
EXPOSE 8000

# Default command runs the FastAPI app with gunicorn using uvicorn workers
# Adjust --workers to match available CPU/memory for production
CMD ["gunicorn", "websearch:app", "-k", "uvicorn.workers.UvicornWorker", "-b", "0.0.0.0:8000", "--workers", "2", "--threads", "4", "--log-level", "info"]
