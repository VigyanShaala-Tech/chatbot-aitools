import json
import logging
from datetime import datetime
from typing import Dict, Optional

from fastapi import APIRouter, HTTPException, BackgroundTasks, Request
from pydantic import BaseModel

from app.services.openai_client import client
from app.core.config import settings, results_logger
from app.services.glific import resume_contact_flow
from app.core.rate_limit import limiter

logger = logging.getLogger(__name__)
results_log = results_logger

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

    logger.info(f"Starting search processing for query: {query} flow_id={flow_id} contact_id={contact_id}")

    try:
        
        kwargs = dict(
            model=settings.OPENAI_MODEL,
            tools=[{"type": "web_search"}],
            input=query,
        )
        if instructions:
            kwargs["instructions"] = instructions
            
        resp = await client.responses.create(**kwargs)

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
        logger.info(f"OpenAI API call successful flow_id={flow_id} contact_id={contact_id}")

    except Exception as e:
        logger.error(f"OpenAI API error: {e} flow_id={flow_id} contact_id={contact_id}")
        openai_response = f"Error: {str(e)}"

    # Send result to Glific
    result_data = {
        "websearch_response": openai_response,
        "query": query,
        "processed_at": datetime.now().isoformat(),
        "duration_ms": int((datetime.now() - start_time).total_seconds() * 1000)
    }

    # Write a structured result log with flow and contact identifiers
    results_log.info(json.dumps({
        "flow_id": flow_id,
        "contact_id": contact_id,
        "result": result_data,
    }))

    await resume_contact_flow(flow_id, contact_id, result_data)


@router.post("/search", status_code=202)
@limiter.limit("500/minute")
async def search(request: Request, req: QueryRequest, background_tasks: BackgroundTasks) -> Dict[str, str]:
    if not req.query or not req.query.strip():
        raise HTTPException(status_code=400, detail="query cannot be empty")

    logger.info(f"Received search request: {req.model_dump()} flow_id={req.flow_id} contact_id={req.contact_id}")
    background_tasks.add_task(process_search_and_callback, req.model_dump())

    return {
        "status": "accepted",
        "message": "Search request is being processed. Results will be sent to Glific."
    }
