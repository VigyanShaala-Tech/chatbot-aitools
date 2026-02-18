import base64
import json
import logging
from datetime import datetime
from typing import Dict, Optional, Any

import httpx
from fastapi import APIRouter, HTTPException, BackgroundTasks, Request
from pydantic import BaseModel, model_validator
from tenacity import retry, stop_after_attempt, wait_exponential, before_sleep_log

from app.services.openai_client import client
from app.core.config import settings, results_logger
from app.services.glific import resume_contact_flow
from app.core.rate_limit import limiter

logger = logging.getLogger(__name__)
results_log = results_logger

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

@retry(
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
async def analyze_file_with_openai(file_url: str, prompt: str) -> str:
    """Download a file and send it to OpenAI for analysis. Retries up to 2 times with exponential backoff."""
    MAX_FILE_SIZE = 100 * 1024 * 1024  # 100 MB

    # Step 1: Download the file content
    async with httpx.AsyncClient() as http_client:
        resp = await http_client.get(file_url)
        resp.raise_for_status()

        content_type = resp.headers.get("content-type") or "application/octet-stream"
        file_data = resp.content
        filename = file_url.split("/")[-1] or "file.bin"

    # Validate content type is PDF
    if "application/pdf" not in content_type:
        raise ValueError(f"Only PDF files are supported. Received content-type: {content_type}")

    # Validate file size
    if len(file_data) > MAX_FILE_SIZE:
        size_mb = len(file_data) / (1024 * 1024)
        raise ValueError(f"File size {size_mb:.1f}MB exceeds the 100MB limit")

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

    return "\n\n".join(pieces) if pieces else None


@retry(
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
async def send_result_to_glific(flow_id: str, contact_id: str, result_data: dict):
    """Send the processed result to Glific. Retries up to 3 times with exponential backoff."""
    results_log.info(json.dumps({
        "flow_id": flow_id,
        "contact_id": contact_id,
        "result": result_data,
    }))
    await resume_contact_flow(flow_id, contact_id, result_data)


async def process_file_and_callback(request_data: dict):
    start_time = datetime.now()

    file_url = request_data["file_url"]
    prompt = request_data["prompt"]
    flow_id = request_data["flow_id"]
    contact_id = request_data["contact_id"]

    logger.info(f"Starting file processing for {file_url} with prompt: {prompt} flow_id={flow_id} contact_id={contact_id}")

    try:
        openai_response = await analyze_file_with_openai(file_url, prompt)
        logger.info(f"OpenAI API call successful flow_id={flow_id} contact_id={contact_id}")
    except Exception as e:
        logger.error(f"Error processing file after retries: {e} flow_id={flow_id} contact_id={contact_id}")
        openai_response = f"Error: {str(e)}"

    result_data = {
        "pdf_response": openai_response,
        "query": prompt,
        "file_url": file_url,
        "processed_at": datetime.now().isoformat(),
        "duration_ms": int((datetime.now() - start_time).total_seconds() * 1000),
    }

    try:
        await send_result_to_glific(flow_id, contact_id, result_data)
    except Exception as e:
        logger.error(f"Failed to send result to Glific after retries: {e} flow_id={flow_id} contact_id={contact_id}")


@router.post("/analyze-file", status_code=202)
@limiter.limit("500/minute")
async def analyze_file(request: Request, req: FileAnalysisRequest, background_tasks: BackgroundTasks) -> Dict[str, str]:
    if not req.file_url:
        raise HTTPException(status_code=400, detail="file_url is required")

    logger.info(f"Received file analysis request: {req.model_dump()} flow_id={req.flow_id} contact_id={req.contact_id}")
    background_tasks.add_task(process_file_and_callback, req.model_dump())

    return {
        "status": "accepted",
        "message": "File is being processed. Results will be sent to Glific."
    }
