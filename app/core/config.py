import os
import logging
from logging.handlers import RotatingFileHandler
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_BASE_URL: str = os.getenv("OPENAI_BASE_URL", "")
    VS_API_KEY: str = os.getenv("VS_API_KEY", "default-insecure-key-change-me")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-5")
    GLIFIC_API_URL: str = os.getenv("GLIFIC_API_URL", "")
    GLIFIC_PHONE: str = os.getenv("GLIFIC_PHONE", "")
    GLIFIC_PASSWORD: str = os.getenv("GLIFIC_PASSWORD", "")
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "/app/logs/web.log"
    RESULT_LOG_FILE: str = "/app/logs/results.log"

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )

settings = Settings()

# Configure logging
log_handlers = [logging.StreamHandler()]

if settings.LOG_FILE:
    log_dir = os.path.dirname(settings.LOG_FILE)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)
    log_handlers.append(
        RotatingFileHandler(settings.LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3)
    )

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=log_handlers,
)
logger = logging.getLogger(__name__)

# Dedicated results logger
results_logger = logging.getLogger("app.results")
results_logger.setLevel(getattr(logging, settings.LOG_LEVEL))

if settings.RESULT_LOG_FILE:
    res_dir = os.path.dirname(settings.RESULT_LOG_FILE)
    if res_dir and not os.path.exists(res_dir):
        os.makedirs(res_dir, exist_ok=True)
    res_handler = RotatingFileHandler(settings.RESULT_LOG_FILE, maxBytes=20 * 1024 * 1024, backupCount=5)
    res_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    res_handler.setFormatter(res_formatter)
    results_logger.addHandler(res_handler)
