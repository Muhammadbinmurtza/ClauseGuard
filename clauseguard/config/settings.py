"""Application configuration loaded from environment variables."""

import os
from typing import Final

from dotenv import load_dotenv

load_dotenv()

DEEPSEEK_API_KEY: str = os.environ.get("DEEPSEEK_API_KEY", "")
BASE_URL: str = os.environ.get("BASE_URL", "https://api.deepseek.com")
MODEL_NAME: str = os.environ.get("MODEL_NAME", "deepseek-chat")
MAX_TOKENS: Final[int] = 4096
TIMEOUT_SECONDS: Final[int] = 90
MAX_CLAUSES: Final[int] = 60

TEMPERATURE: Final[float] = 0.0


def validate_config() -> None:
    """Validate that all required configuration is present.

    Raises:
        ValueError: If DEEPSEEK_API_KEY is not set.
    """
    if not DEEPSEEK_API_KEY:
        raise ValueError(
            "DEEPSEEK_API_KEY is not set. Please set it in your .env file "
            "or environment variables."
        )
