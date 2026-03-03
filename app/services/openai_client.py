import logging
import os
from openai import AsyncOpenAI
from app.core.config import settings

logger = logging.getLogger(__name__)

client_kwargs = {
	"api_key": settings.OPENAI_API_KEY,
	"timeout": 120.0,
}

# Only set base_url if non-empty after stripping to avoid blank overrides
base_url = settings.OPENAI_BASE_URL.strip() if settings.OPENAI_BASE_URL else None
if base_url:
	client_kwargs["base_url"] = base_url

client = AsyncOpenAI(**client_kwargs)

logger.info(
	"OpenAI client initialized",
	extra={
		"base_url": getattr(client, "base_url", None),
		"has_custom_base": bool(base_url),
	},
)

