import os
import random
import string
import time
import uuid
import json
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from locust import HttpUser, task, between, events

# --- Configuration ---
MOCK_SERVER_PORT = 5050
MOCK_OPENAI_PORT = 5051
API_KEY = os.getenv("API_KEY", "your-secret-api-key")
LOG_FILE = "transaction_logs.jsonl"

# --- State Management ---
# Stores context for in-flight requests: {flow_id: {start_time, request, initial_response}}
REQUEST_TRACKER = {}
TRACKER_LOCK = threading.Lock()
LOG_LOCK = threading.Lock()

def log_transaction(record):
    """Thread-safe append to the transaction log file."""
    with LOG_LOCK:
        with open(LOG_FILE, "a") as f:
            f.write(json.dumps(record) + "\n")

# --- Mock Glific Server ---
class MockGlificHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        # Handle Login (return fake token)
        if self.path == "/v1/session":
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({
                "data": {"access_token": "fake-load-test-token"}
            }).encode())
            return

        # Handle GraphQL Mutation (The Callback)
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)
        
        try:
            body = json.loads(post_data.decode('utf-8'))
            variables = body.get("variables", {})
            flow_id = variables.get("flowId")
            
            # Match with tracker
            context = None
            if flow_id:
                with TRACKER_LOCK:
                    context = REQUEST_TRACKER.pop(flow_id, None)
                
            if context:
                duration_ms = (time.time() - context["start_time"]) * 1000
                
                # Create Full Transaction Record
                full_record = {
                    "flow_id": flow_id,
                    "endpoint": context["endpoint"],
                    "start_time": datetime_str(context["start_time"]),
                    "duration_ms": duration_ms,
                    "request": context["request"],
                    "initial_api_response": context["initial_response"],
                    "glific_callback": body
                }
                log_transaction(full_record)

                # Report success to Locust
                events.request.fire(
                    request_type="Async Callback",
                    name="Glific Notification",
                    response_time=duration_ms,
                    response_length=content_length,
                    exception=None,
                    context=None
                )
            
            # Always return success to the app
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({
                "data": {"resumeContactFlow": {"success": True, "errors": []}}
            }).encode())

        except Exception as e:
            # Report failure if we crash
            events.request.fire(
                request_type="Async Callback",
                name="Glific Notification",
                response_time=0,
                response_length=0,
                exception=e,
                context=None
            )
            self.send_response(500)
            self.end_headers()

    def log_message(self, format, *args):
        return

def run_mock_server():
    server = HTTPServer(('0.0.0.0', MOCK_SERVER_PORT), MockGlificHandler)
    print(f"Mock Glific Server started on port {MOCK_SERVER_PORT}")
    server.serve_forever()

def datetime_str(timestamp):
    return time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(timestamp))

# Start mock server
server_thread = threading.Thread(target=run_mock_server, daemon=True)
server_thread.start()


# --- Mock OpenAI API ---
class MockOpenAIHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path.rstrip("/") == "/v1/responses":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)

            try:
                payload = json.loads(body.decode("utf-8") or "{}")
            except json.JSONDecodeError:
                payload = {}

            mock_text = self._extract_text_hint(payload) or "Mocked OpenAI response"

            response_body = {
                "id": f"resp_{uuid.uuid4().hex[:8]}",
                "object": "response",
                "created": int(time.time()),
                "model": payload.get("model", "mock-model"),
                "output": [
                    {
                        "content": [
                            {
                                "type": "output_text",
                                "text": mock_text,
                            }
                        ]
                    }
                ],
            }

            response_bytes = json.dumps(response_body).encode()

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(response_bytes)))
            self.end_headers()
            self.wfile.write(response_bytes)
            return

        self.send_response(404)
        self.end_headers()

    def _extract_text_hint(self, payload):
        input_payload = payload.get("input")

        if isinstance(input_payload, str):
            return f"Mocked response for query: {input_payload}"

        if isinstance(input_payload, list):
            for item in input_payload:
                if not isinstance(item, dict):
                    continue

                content_list = item.get("content") or []
                for content in content_list:
                    if isinstance(content, dict) and content.get("type") in ("input_text", "text"):
                        text_val = content.get("text")
                        if text_val:
                            return f"Mocked response for query: {text_val}"

        instructions = payload.get("instructions")
        if instructions:
            return f"Mocked response for instructions: {instructions}"

        return None

    def log_message(self, format, *args):
        return


def run_mock_openai_server():
    server = HTTPServer(("0.0.0.0", MOCK_OPENAI_PORT), MockOpenAIHandler)
    print(f"Mock OpenAI API started on port {MOCK_OPENAI_PORT}")
    server.serve_forever()


openai_thread = threading.Thread(target=run_mock_openai_server, daemon=True)
openai_thread.start()


# --- Locust User ---
class ChatbotUser(HttpUser):
    wait_time = between(2, 5)

    def on_start(self):
        self.client.headers.update({"X-API-KEY": API_KEY})

    @task(3)
    def search_query(self):
        flow_id = str(uuid.uuid4())
        
        stem_questions = [
            "Why is the sky blue?",
            "How do plants eat?",
            "What makes a volcano erupt?",
            "Why do stars twinkle?",
            "How do birds fly?",
            "What is gravity?",
            "Why does ice float?",
            "How do magnets work?",
            "What is a black hole?",
            "Why do leaves change color in fall?",
            "How big is the universe?",
            "What are clouds made of?",
            "Why is the ocean salty?",
            "How do computers think?",
            "What is DNA?",
            "Why do we need sleep?",
            "How does the moon change shape?",
            "What is electricity?",
            "How are rainbows formed?",
            "Why do cheetahs run so fast?"
        ]
        
        question = random.choice(stem_questions)
        
        payload = {
            "query": question,
            "flow_id": flow_id,
            "contact_id": f"contact_{flow_id[:8]}",
            "instructions": "Keep it brief and simple for a child"
        }
        
        start_ts = time.time()
        
        # Initial Request
        with self.client.post("/search", json=payload, catch_response=True) as response:
            resp_content = None
            try:
                resp_content = response.json()
            except:
                resp_content = response.text

            if response.status_code == 202:
                # Store context for the callback
                with TRACKER_LOCK:
                    REQUEST_TRACKER[flow_id] = {
                        "start_time": start_ts,
                        "endpoint": "search",
                        "request": payload,
                        "initial_response": resp_content
                    }
            else:
                response.failure(f"Status {response.status_code}")

    @task(1)
    def analyze_file(self):
        flow_id = str(uuid.uuid4())
        # Use a stable URL or one that you know works
        
        file_url = "https://filemanager.gupshup.io/wa/ab0b21d3-311b-43af-8b37-c80705a428d8/wa/media/2586674838383070?download=false&fileName=PDF+document.pdf"
        
        payload = {
            "file_url": file_url,
            "prompt": "Summarize",
            "flow_id": flow_id,
            "contact_id": f"contact_{flow_id[:8]}"
        }
        
        start_ts = time.time()
            
        with self.client.post("/analyze-file", json=payload, catch_response=True) as response:
            resp_content = None
            try:
                resp_content = response.json()
            except:
                resp_content = response.text

            if response.status_code == 202:
                with TRACKER_LOCK:
                    REQUEST_TRACKER[flow_id] = {
                        "start_time": start_ts,
                        "endpoint": "analyze_file",
                        "request": payload,
                        "initial_response": resp_content
                    }
            else:
                response.failure(f"Status {response.status_code}")

if __name__ == "__main__":
    import os
    os.system("locust -f locustfile.py")
