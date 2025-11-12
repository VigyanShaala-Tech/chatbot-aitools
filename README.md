# chatbot-websearch
PoC to integrate OpenAI's websearch with Glific

## Run

$ export OPENAI_API_KEY="sk-..."
$ pip install -r requirements.txt
$ python websearch.py

## Usage

$ curl -v -X POST "http://localhost:8000/search" \
  -H "Content-Type: application/json" \
  -d '{"query":"tell me the date today"}'
