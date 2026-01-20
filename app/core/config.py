import os
import logging
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_BASE_URL: str = os.getenv("OPENAI_BASE_URL", "")
    API_KEY: str = os.getenv("API_KEY", "default-insecure-key-change-me")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-5")
    GLIFIC_API_URL: str = os.getenv("GLIFIC_API_URL", "")
    GLIFIC_PHONE: str = os.getenv("GLIFIC_PHONE", "")
    GLIFIC_PASSWORD: str = os.getenv("GLIFIC_PASSWORD", "")
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "/app/logs/websearch.log"

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )

settings = Settings()

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(settings.LOG_FILE) if os.path.exists(os.path.dirname(settings.LOG_FILE)) else logging.NullHandler()
    ]
)
logger = logging.getLogger(__name__)
