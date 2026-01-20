import logging
import os
from openai import AsyncOpenAI
from app.core.config import settings

logger = logging.getLogger(__name__)

client_kwargs = {
	"api_key": settings.OPENAI_API_KEY,
	"timeout": 120.0,
}

# Allow redirecting to a mock server during load tests
if settings.OPENAI_BASE_URL:
	logger.info(f"OpenAI client initialized {settings.OPENAI_BASE_URL}",)
	client_kwargs["base_url"] = settings.OPENAI_BASE_URL

client = AsyncOpenAI(**client_kwargs)

