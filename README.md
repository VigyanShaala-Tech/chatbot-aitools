# chatbot-websearch
PoC to integrate OpenAI's websearch with Glific

## Run

$ export OPENAI_API_KEY="sk-..."

$ pip install -r requirements.txt

$ python websearch.py


## Usage

$ curl -v -X POST "http://localhost:8000/search" -H "Content-Type: application/json" -d '{"query":"tell me the date today"}'

# Dockerization

Build and run locally

1. Build image:

```zsh
docker build -t chatbot-websearch .
```

2. Run container (pass your key at runtime):

```zsh
docker run -e OPENAI_API_KEY="$OPENAI_API_KEY" -p 8000:8000 chatbot-websearch
```

Or using docker-compose (reads `OPENAI_API_KEY` from your environment):

```zsh
export OPENAI_API_KEY="sk-..."
docker-compose up --build
```

The app will be reachable at `http://localhost:8000/search`.
