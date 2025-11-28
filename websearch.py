import os
import logging
from typing import Dict
from datetime import datetime
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
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
    flow_id: str
    contact_id: str


async def get_auth_token() -> str:
    """Get authentication token from Glific API"""
    login_url = os.getenv("GLIFIC_LOGIN_URL")
    phone = os.getenv("GLIFIC_PHONE")
    password = os.getenv("GLIFIC_PASSWORD")

    if not all([login_url, phone, password]):
        raise ValueError("Missing Glific credentials in environment variables")

    try:
        async with httpx.AsyncClient(timeout=30.0) as http_client:
            response = await http_client.post(
                login_url,
                json={
                    "user": {
                        "phone": phone,
                        "password": password
                    }
                },
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json"
                }
            )
            response.raise_for_status()
            data = response.json()
            access_token = data["data"]["access_token"]
            logger.info("Successfully obtained auth token")
            return access_token
    except Exception as e:
        logger.error(f"Failed to get auth token: {e}")
        raise


async def process_search_and_callback(request_data: dict):
    """Background task to process search and send results to Glific"""
    start_time = datetime.now()

    query = request_data["query"]
    flow_id = request_data["flow_id"]
    contact_id = request_data["contact_id"]

    logger.info(f"Starting search processing for query: {query}")

    # Step 1: Call OpenAI API
    try:
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

        openai_response = "\n\n".join(pieces) if pieces else None
        logger.info("OpenAI API call successful")

    except Exception as e:
        logger.error(f"OpenAI API error: {e}")
        openai_response = f"Error: {str(e)}"

    # Step 2: Get auth token from Glific
    try:
        auth_token = await get_auth_token()
    except Exception as e:
        logger.error(f"Failed to authenticate with Glific: {e}")
        return

    # Step 3: Send result to Glific via GraphQL mutation
    try:
        glific_api_url = os.getenv("GLIFIC_API_URL")
        if not glific_api_url:
            raise ValueError("GLIFIC_API_URL not set in environment")

        # Prepare result payload
        result_data = {
            **request_data,
            "openai_response": openai_response,
            "processed_at": datetime.now().isoformat(),
            "duration_ms": int((datetime.now() - start_time).total_seconds() * 1000)
        }

        # GraphQL mutation
        graphql_query = {
            "query": """mutation resumeContactFlow($flowId: ID!, $contactId: ID!, $result: Json!) {
  resumeContactFlow(flowId: $flowId, contactId: $contactId, result: $result) {
    success
    errors {
        key
        message
    }
  }
}""",
            "variables": {
                "flowId": flow_id,
                "contactId": contact_id,
                "result": result_data
            }
        }

        async with httpx.AsyncClient(timeout=30.0) as http_client:
            response = await http_client.post(
                glific_api_url,
                json=graphql_query,
                headers={
                    "authorization": auth_token,
                    "Content-Type": "application/json"
                }
            )
            response.raise_for_status()
            result = response.json()
            logger.info(f"Successfully sent result to Glific: {result}")

    except Exception as e:
        logger.error(f"Failed to send result to Glific: {e}")


@app.post("/search", status_code=202)
async def search(req: QueryRequest, background_tasks: BackgroundTasks) -> Dict[str, str]:
    if not req.query or not req.query.strip():
        raise HTTPException(status_code=400, detail="query cannot be empty")

    # Log the complete received request
    logger.info(f"Received search request: {req.model_dump()}")

    # Convert request to dict to pass all parameters to background task
    request_data = req.model_dump()

    # Add background task to process search and send to Glific
    background_tasks.add_task(
        process_search_and_callback,
        request_data
    )

    return {
        "status": "accepted",
        "message": "Search request is being processed. Results will be sent to Glific."
    }


@app.get("/health")
async def health() -> Dict[str, str]:
    """Simple health check endpoint used by container healthchecks."""
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run("websearch:app", host="0.0.0.0", port=8000, reload=False)