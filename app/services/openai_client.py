from openai import AsyncOpenAI
from app.core.config import settings

# Initialize OpenAI client
client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY, timeout=120.0)
