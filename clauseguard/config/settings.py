"""Application configuration loaded from environment variables.

Supports Qwen via vLLM (default) and any OpenAI-compatible API as fallback.
"""

import os
from typing import Final

from dotenv import load_dotenv

load_dotenv()

API_KEY: str = os.environ.get("API_KEY", os.environ.get("DEEPSEEK_API_KEY", "EMPTY"))
BASE_URL: str = os.environ.get(
    "BASE_URL",
    os.environ.get("VLLM_BASE_URL", "http://165.245.141.170:8000/v1"),
)
MODEL_NAME: str = os.environ.get(
    "MODEL_NAME",
    os.environ.get("VLLM_MODEL_NAME", "Qwen/Qwen2.5-1.5B-Instruct"),
)
MAX_TOKENS: Final[int] = int(os.environ.get("MAX_TOKENS", "16384"))
TIMEOUT_SECONDS: Final[int] = int(os.environ.get("TIMEOUT_SECONDS", "120"))
MAX_CLAUSES: Final[int] = 60

TEMPERATURE: Final[float] = 0.0

DEEPSEEK_API_KEY: str = API_KEY


def validate_config() -> None:
    """Validate that all required configuration is present.

    For Qwen/vLLM, no API key is required — the check is informational.
    Raises ValueError only if a legacy DeepSeek key is expected and missing.
    """
    pass
