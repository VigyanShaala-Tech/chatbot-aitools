import logging
from openai import AsyncOpenAI
from app.core.config import settings

logger = logging.getLogger(__name__)

client_kwargs = {
	"api_key": settings.OPENAI_API_KEY,
	"timeout": 120.0,
}

# Allow redirecting to a mock server during load tests
if settings.OPENAI_BASE_URL:
	client_kwargs["base_url"] = settings.OPENAI_BASE_URL

client = AsyncOpenAI(**client_kwargs)
logger.info(
	"OpenAI client initialized",
	extra={
		"openai_base_url_setting": settings.OPENAI_BASE_URL,
		"client_kwargs": client_kwargs,
	},
)
