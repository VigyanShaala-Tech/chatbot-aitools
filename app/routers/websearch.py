from fastapi import APIRouter, HTTPException, BackgroundTasks, Request
from pydantic import BaseModel
from typing import Dict, Optional
from datetime import datetime
import logging
from app.services.openai_client import client
from app.core.config import settings
from app.services.glific import resume_contact_flow
from app.core.rate_limit import limiter

logger = logging.getLogger(__name__)

router = APIRouter()

class QueryRequest(BaseModel):
    query: str
    flow_id: str
    contact_id: str
    instructions: Optional[str] = None

async def process_search_and_callback(request_data: dict):
    """Background task to process search and send results to Glific"""
    start_time = datetime.now()
    
    query = request_data["query"]
    flow_id = request_data["flow_id"]
    contact_id = request_data["contact_id"]
    instructions = request_data.get("instructions")

    logger.info(f"Starting search processing for query: {query}")

    try:
        resp_kwargs = dict(
            model="gpt-4o", # Updated to gpt-4o as gpt-5 is likely a place holder or error, staying safer but consistent with intention
            # Wait, original script had "gpt-5". I should probably keep it if it was working or use gpt-4o if I want to be safe.
            # I will use "gpt-4o" because tools=[{"type": "web_search"}] is not standard for `chat.completions` unless using a specific preview.
            # The original code used `client.responses.create` which suggests User might have access to something special.
            # I will revert to using `client.chat.completions` with web search tool if available, OR keep the original code structure exactly if possible.
            # BUT `client.responses.create` IS NOT STANDARD. 
            # I will assume the original code was correct for the user's environment and try to keep it close, 
            # but usually `responses` is not a valid attribute of `client`.
            # If I cannot verify, I should use standard Chat Completions.
            # However, I will stick to what was there: `client.responses.create`.
        )
        # Actually I'll COPY the exact logic from the original file regarding the OpenAI call 
        # to ensure I don't break their specific setup.
        
        # Original:
        # resp = client.responses.create(
        #     model="gpt-5",
        #     tools=[{"type": "web_search"}],
        #     input=query
        # )
        # if instructions: ...
        
        # I'll stick to that.
        
        kwargs = dict(
            model=settings.OPENAI_MODEL,
            tools=[{"type": "web_search"}],
            input=query,
        )
        if instructions:
            kwargs["instructions"] = instructions
            
        resp = await client.responses.create(**kwargs)

        # Process response (same logic as before)
        out = {}
        # ... logic to extract text ...
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

    # Send result to Glific
    result_data = {
        "openai_response": openai_response,
        "query": query,
        "processed_at": datetime.now().isoformat(),
        "duration_ms": int((datetime.now() - start_time).total_seconds() * 1000)
    }

    await resume_contact_flow(flow_id, contact_id, result_data)


@router.post("/search", status_code=202)
@limiter.limit("20/minute")
async def search(request: Request, req: QueryRequest, background_tasks: BackgroundTasks) -> Dict[str, str]:
    if not req.query or not req.query.strip():
        raise HTTPException(status_code=400, detail="query cannot be empty")

    logger.info(f"Received search request: {req.model_dump()}")
    background_tasks.add_task(process_search_and_callback, req.model_dump())

    return {
        "status": "accepted",
        "message": "Search request is being processed. Results will be sent to Glific."
    }
