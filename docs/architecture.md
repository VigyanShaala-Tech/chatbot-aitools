# Chatbot Websearch Architecture

## What the app does
- Receives requests from a WhatsApp bot (via Glific) to search the web or analyze a file.
- Uses OpenAI to generate an answer or summary.
- Sends the result back to Glific so it can message the user in WhatsApp.

## Components
- FastAPI app (our server)
- OpenAI API (brains: search and file understanding)
- Glific API (messaging: delivers results to WhatsApp users)
- Optional mocks (for load tests): mock Glific and mock OpenAI
- Logs: main app log and results log

## Key environment settings
- OPENAI_API_KEY: real key used in production
- OPENAI_BASE_URL: leave empty in production; set to mock URL only in tests
- GLIFIC_API_URL, GLIFIC_PHONE, GLIFIC_PASSWORD: Glific credentials
- LOG_FILE (default /app/logs/web.log) and RESULT_LOG_FILE (default /app/logs/results.log)

## High-level data flows

Search flow (text question)
```
User on WhatsApp -> Glific -> Our FastAPI /search (202 Accepted)
                                   | background task
                                   v
                               OpenAI (web search + answer)
                                   |
                                   v
                              Our FastAPI -> Glific callback -> User on WhatsApp
```

File analysis flow (PDF or other file)
```
User uploads image on Whatsapp -> Glific -> Our FastAPI /analyze-file (202 Accepted)
                                   | background task
                                   v
                          Download file from provided URL
                                   |
                                   v
                         OpenAI (file input + summary)
                                   |
                                   v
                              Our FastAPI -> Glific callback -> User on WhatsApp
```

## What happens inside the app
1) FastAPI receives the request and immediately returns 202 so the user is not waiting.
2) A background task starts:
   - For /search: send the question to OpenAI with web_search tool enabled.
   - For /analyze-file: download the file, convert to data URI, send to OpenAI file input.
3) The OpenAI response text is collected.
4) The app calls Glific (resumeContactFlow) with the answer/summary, the flow id, and the contact id.
5) Logs are written to:
   - web.log: general app events (requests, errors)
   - results.log: structured entries with flow_id, contact_id, and the result payload sent to Glific

## Deployment modes
- Production: do not set OPENAI_BASE_URL (defaults to api.openai.com). Use real keys.
- Load testing: set OPENAI_BASE_URL to the mock OpenAI URL and point Glific calls to the mock Glific server. This prevents real API spend.

## Simple visual of components
```
         +----------------+
         |   WhatsApp     |
         +-------+--------+
                 |
                 v
           +-----+------+
           |    Glific  |
           +-----+------+
                 |
   /search or    v   callback
   /analyze-file +------------+
                 | FastAPI app|
                 +------+-----+
                        |
                        v
                +-------+-------+
                |    OpenAI     |
                +---------------+
```

## Error handling and retries
- If OpenAI or Glific fails, the app logs the error with flow_id/contact_id; the background task reports the error text back to Glific so the user is informed.

## Logging and observability
- Both logs rotate to avoid disk growth (sizes: 10MB for app log, 20MB for results log).
- Mount /app/logs to the host in Docker Compose to collect logs outside the container.

## Security notes
- Keep OPENAI_API_KEY and Glific credentials out of source control; set them via environment variables.
- Do not set OPENAI_BASE_URL in production unless intentionally pointing to a controlled endpoint.
