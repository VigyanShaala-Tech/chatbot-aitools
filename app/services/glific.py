import httpx
import json
import logging
from typing import Dict, Any
from app.core.config import settings

logger = logging.getLogger(__name__)

async def get_auth_token() -> str:
    """Get authentication token from Glific API"""
    api_url = settings.GLIFIC_API_URL
    phone = settings.GLIFIC_PHONE
    password = settings.GLIFIC_PASSWORD

    if not all([api_url, phone, password]):
        raise ValueError("Missing Glific credentials in environment variables")

    login_url = f"{api_url}/v1/session"

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
            return access_token
    except Exception as e:
        logger.error(f"Failed to get auth token: {e}")
        raise

async def resume_contact_flow(flow_id: str, contact_id: str, result_data: Dict[str, Any]):
    """Send result to Glific via GraphQL mutation"""
    try:
        auth_token = await get_auth_token()
    except Exception as e:
        logger.error(f"Failed to authenticate with Glific: {e}")
        return

    try:
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
                "result": json.dumps(result_data)
            }
        }

        async with httpx.AsyncClient(timeout=30.0) as http_client:
            response = await http_client.post(
                settings.GLIFIC_API_URL,
                json=graphql_query,
                headers={
                    "authorization": auth_token,
                    "Content-Type": "application/json"
                }
            )
            response.raise_for_status()
            result = response.json()
            logger.info(f"Successfully sent result to Glific: {result}")
            return result

    except Exception as e:
        logger.error(f"Failed to send result to Glific: {e}")
        raise
