# chatbot-websearch

FastAPI service that integrates OpenAI's web search capabilities with Glific for WhatsApp chatbot interactions.

## Features

- Async web search using OpenAI GPT-5 with web search tools
- Background task processing for non-blocking API responses
- Glific API integration with GraphQL mutations
- Docker support with Python 3.13 and uv for fast dependency installation
- Comprehensive logging to both console and file
- Health check endpoint for monitoring

## Prerequisites

- Python 3.13+ (for local development)
- Docker and Docker Compose (for containerized deployment)
- OpenAI API key
- Glific account credentials

## Environment Variables

Create a `.env` file in the project root (see `.env.example` for reference):

```bash
# OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key_here

# Glific Configuration
GLIFIC_API_URL=https://api.staging.glific.com/api
GLIFIC_PHONE=917834811114
GLIFIC_PASSWORD=secret1234
```

## Local Development

### Setup

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Set environment variables:

```bash
export OPENAI_API_KEY="sk-..."
export GLIFIC_API_URL="https://api.staging.glific.com/api"
export GLIFIC_PHONE="917834811114"
export GLIFIC_PASSWORD="secret1234"
```

3. Create logs directory:

```bash
mkdir -p logs
```

4. Run the application:

```bash
python websearch.py
```

The API will be available at `http://localhost:8000`.

### Development with auto-reload

```bash
uvicorn websearch:app --host 0.0.0.0 --port 8000 --reload
```

## Docker Deployment

### Using Docker Compose (Recommended)

1. Set environment variables in your shell or create a `.env` file:

```bash
export OPENAI_API_KEY="sk-..."
export GLIFIC_API_URL="https://api.staging.glific.com/api"
export GLIFIC_PHONE="917834811114"
export GLIFIC_PASSWORD="secret1234"
```

2. Build and start the service:

```bash
docker-compose up --build
```

The API will be available at `http://localhost:3001` (mapped from container port 8000).

3. Stop the service:

```bash
docker-compose down
```

### Using Docker directly

1. Build the image:

```bash
docker build -t chatbot-websearch .
```

2. Run the container:

```bash
docker run -d \
  -e OPENAI_API_KEY="$OPENAI_API_KEY" \
  -e GLIFIC_API_URL="$GLIFIC_API_URL" \
  -e GLIFIC_PHONE="$GLIFIC_PHONE" \
  -e GLIFIC_PASSWORD="$GLIFIC_PASSWORD" \
  -p 3001:8000 \
  --name chatbot-websearch \
  chatbot-websearch
```

3. View logs:

```bash
docker logs -f chatbot-websearch
```

## API Usage

### Search Endpoint

Initiates an async web search and sends results to Glific via GraphQL mutation.

**Request:**

```bash
curl -X POST "http://localhost:3001/search" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is the latest news about AI?",
    "flow_id": "123",
    "contact_id": "456"
  }'
```

**Response (202 Accepted):**

```json
{
  "status": "accepted",
  "message": "Search request is being processed. Results will be sent to Glific."
}
```

The service will:
1. Return immediate acknowledgment (202 status)
2. Process OpenAI web search in the background
3. Authenticate with Glific API
4. Send results via GraphQL `resumeContactFlow` mutation

### Health Check Endpoint

```bash
curl http://localhost:3001/health
```

**Response:**

```json
{
  "status": "ok"
}
```

## Architecture

```
┌─────────────┐     POST /search      ┌──────────────────┐
│   Client    │ ───────────────────> │   FastAPI App    │
│  (Glific)   │ <─ 202 Accepted ───  │                  │
└─────────────┘                       └──────────────────┘
                                              │
                                              │ Background Task
                                              ▼
                                      ┌──────────────────┐
                                      │   OpenAI API     │
                                      │   (GPT-5 +       │
                                      │   Web Search)    │
                                      └──────────────────┘
                                              │
                                              ▼
                                      ┌──────────────────┐
                                      │   Glific API     │
                                      │   (GraphQL)      │
                                      └──────────────────┘
```

## Logging

Logs are written to:
- **Console**: Standard output (visible in `docker logs`)
- **File**: `/app/logs/websearch.log` (inside container)

Log format: `%(asctime)s - %(name)s - %(levelname)s - %(message)s`

To view logs in Docker:

```bash
# Console logs
docker logs -f chatbot-websearch

# File logs (exec into container)
docker exec -it chatbot-websearch cat /app/logs/websearch.log
```

## Configuration

### Timeouts

- **OpenAI API**: 120 seconds (2 minutes)
- **Gunicorn workers**: 180 seconds (3 minutes)
- **HTTP callbacks**: 30 seconds

### Gunicorn Workers

Default configuration: 2 workers, 4 threads per worker

Adjust in `Dockerfile` CMD based on available CPU/memory:

```dockerfile
CMD ["gunicorn", "websearch:app", "-k", "uvicorn.workers.UvicornWorker", \
     "-b", "0.0.0.0:8000", "--workers", "4", "--threads", "8", \
     "--timeout", "180", "--log-level", "info"]
```

## Troubleshooting

### Worker timeout errors

If you see `WORKER TIMEOUT` errors, increase the timeout in `Dockerfile`:

```dockerfile
CMD ["gunicorn", ..., "--timeout", "240", ...]
```

### Missing Glific credentials

Ensure all environment variables are exported before running:

```bash
docker-compose down
export GLIFIC_API_URL="..."
export GLIFIC_PHONE="..."
export GLIFIC_PASSWORD="..."
docker-compose up --build
```

### OpenAI timeout errors

The OpenAI client has a 120-second timeout. For longer operations, increase in `websearch.py`:

```python
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"), timeout=180.0)
```

## Production Deployment

This service is configured for deployment on Render.com via `render.yaml`. The configuration uses Python 3.13 and auto-deploys from the main branch.

Environment variables must be set in the Render dashboard:
- `OPENAI_API_KEY`
- `GLIFIC_API_URL`
- `GLIFIC_PHONE`
- `GLIFIC_PASSWORD`

## License

MIT
