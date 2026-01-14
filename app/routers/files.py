from fastapi import APIRouter, HTTPException, BackgroundTasks, Request
from pydantic import BaseModel, model_validator
import json
from typing import Dict, Optional, Any
from datetime import datetime
import logging
import httpx
import base64
from app.services.openai_client import client
from app.core.config import settings
from app.services.glific import resume_contact_flow
from app.core.rate_limit import limiter

logger = logging.getLogger(__name__)

router = APIRouter()

class FileAnalysisRequest(BaseModel):
    file_url: str
    prompt: Optional[str] = "Analyze this file"
    flow_id: str
    contact_id: str

    @model_validator(mode='before')
    @classmethod
    def parse_string_input(cls, data: Any) -> Any:
        logger.info(f"Validator received data type: {type(data)}")
        if isinstance(data, (str, bytes)):
            try:
                logger.info("Attempting to parse JSON string/bytes")
                parsed = json.loads(data)
                logger.info("Successfully parsed JSON")
                return parsed
            except json.JSONDecodeError:
                logger.error("Failed to parse JSON string")
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
        openai_response = ""

        # Step 1: Download the file content
        async with httpx.AsyncClient() as http_client:
            resp = await http_client.get(file_url)
            resp.raise_for_status()
            
            # Determine mime type
            content_type = resp.headers.get("content-type") or "application/octet-stream"
            file_data = resp.content
            filename = file_url.split("/")[-1] or "file.bin"

        # Step 2: Encode to Base64
        base64_string = base64.b64encode(file_data).decode("utf-8")
        data_uri = f"data:{content_type};base64,{base64_string}"

        # Step 3: Call OpenAI API with Data URI
        openai_input = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_file",
                        "filename": filename,
                        "file_data": data_uri,
                    },
                    {
                        "type": "input_text",
                        "text": prompt,
                    },
                ],
            },
        ]

        resp = await client.responses.create(
            model=settings.OPENAI_MODEL,
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
@limiter.limit("10/minute")
async def analyze_file(request: Request, req: FileAnalysisRequest, background_tasks: BackgroundTasks) -> Dict[str, str]:
    if not req.file_url:
        raise HTTPException(status_code=400, detail="file_url is required")

    logger.info(f"Received file analysis request: {req.model_dump()}")
    background_tasks.add_task(process_file_and_callback, req.model_dump())

    return {
        "status": "accepted",
        "message": "File is being processed. Results will be sent to Glific."
    }
