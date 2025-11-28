import os
import logging
from typing import Dict
from datetime import datetime
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel, HttpUrl
from openai import OpenAI
import uvicorn
import httpx

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# Initialize OpenAI client once at startup for reuse across all requests
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

class QueryRequest(BaseModel):
    query: str
    callback_url: HttpUrl


async def process_search_and_callback(request_data: dict):
    """Background task to process search and send results to callback URL"""
    start_time = datetime.now()
    result = {}

    query = request_data["query"]
    callback_url = request_data["callback_url"]

    logger.info(f"Starting search processing for query: {query}")

    try:
        # Call OpenAI API using global client
        resp = client.responses.create(model="gpt-5", tools=[{"type": "web_search"}], input=query)

        out = {}
        out["model"] = getattr(resp, "model", None)
        out["id"] = getattr(resp, "id", None)
        out["created"] = getattr(resp, "created", None)

        # Extract text content from response
        pieces = []
        for item in getattr(resp, "output", []) or []:
            item = item.to_dict() if hasattr(item, "to_dict") else item
            if isinstance(item, dict):
                for c in item.get("content", []):
                    if isinstance(c, dict) and "text" in c:
                        pieces.append(c["text"])
                    elif isinstance(c, str):
                        pieces.append(c)

        out["text"] = "\n\n".join(pieces) if pieces else None
        result = {"ok": True, "openai_response": out["text"]}
        logger.info("OpenAI API call successful")

    except Exception as e:
        logger.error(f"OpenAI API error: {e}")
        result = {"ok": False, "error": str(e)}

    # Construct callback payload with all original request data
    payload = {
        **request_data,  # Include all original request parameters
        "result": result,
        "processed_at": datetime.now().isoformat(),
        "duration_ms": int((datetime.now() - start_time).total_seconds() * 1000)
    }

    # Send callback
    try:
        async with httpx.AsyncClient(timeout=30.0) as http_client:
            response = await http_client.post(callback_url, json=payload)
            logger.info(f"Callback sent successfully to {callback_url}: {response.status_code}")
    except Exception as e:
        logger.error(f"Callback failed for {callback_url}: {e}")


@app.post("/search", status_code=202)
async def search(req: QueryRequest, background_tasks: BackgroundTasks) -> Dict[str, str]:
    if not req.query or not req.query.strip():
        raise HTTPException(status_code=400, detail="query cannot be empty")

    logger.info(f"Received search request for query: {req.query}")

    # Convert request to dict to pass all parameters to background task
    request_data = req.model_dump()
    # Convert HttpUrl to string for JSON serialization
    request_data["callback_url"] = str(request_data["callback_url"])

    # Add background task to process search and send callback
    background_tasks.add_task(
        process_search_and_callback,
        request_data
    )

    return {
        "status": "accepted",
        "message": "Search request is being processed. Results will be sent to the callback URL."
    }


@app.get("/health")
async def health() -> Dict[str, str]:
    """Simple health check endpoint used by container healthchecks."""
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run("websearch:app", host="0.0.0.0", port=8000, reload=False)