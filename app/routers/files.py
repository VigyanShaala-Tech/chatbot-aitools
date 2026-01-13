from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, model_validator
import json
from typing import Dict, Optional
from datetime import datetime
import logging
import os
from app.services.openai_client import client
from app.services.glific import resume_contact_flow

logger = logging.getLogger(__name__)

router = APIRouter()

class FileAnalysisRequest(BaseModel):
    file_url: str
    prompt: Optional[str] = "Analyze this file"
    flow_id: str
    contact_id: str

    @model_validator(mode='before')
    @classmethod
    def parse_string_input(cls, data: any) -> any:
        if isinstance(data, str):
            try:
                return json.loads(data)
            except json.JSONDecodeError:
                raise ValueError("Invalid JSON string")
        return data

async def process_file_and_callback(request_data: dict):
    start_time = datetime.now()
    
    file_url = request_data["file_url"]
    prompt = request_data["prompt"]
    flow_id = request_data["flow_id"]
    contact_id = request_data["contact_id"]

    logger.info(f"Starting file processing for {file_url} with prompt: {prompt}")

    try:
        # Step 1: Call OpenAI API directly with file URL
        openai_input = [
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": prompt},
                    {
                        "type": "input_file",
                        "file_url": file_url
                    }
                ]
            }
        ]

        resp = client.responses.create(
            model="gpt-5",
            input=openai_input,
        )

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
        logger.error(f"Error processing file: {e}")
        openai_response = f"Error: {str(e)}"

    # Send result to Glific
    result_data = {
        "openai_response": openai_response,
        "query": prompt,
        "file_url": file_url,
        "processed_at": datetime.now().isoformat(),
        "duration_ms": int((datetime.now() - start_time).total_seconds() * 1000)
    }

    await resume_contact_flow(flow_id, contact_id, result_data)


@router.post("/analyze-file", status_code=202)
async def analyze_file(req: FileAnalysisRequest, background_tasks: BackgroundTasks) -> Dict[str, str]:
    if not req.file_url:
        raise HTTPException(status_code=400, detail="file_url is required")

    logger.info(f"Received file analysis request: {req.model_dump()}")
    background_tasks.add_task(process_file_and_callback, req.model_dump())

    return {
        "status": "accepted",
        "message": "File is being processed. Results will be sent to Glific."
    }
