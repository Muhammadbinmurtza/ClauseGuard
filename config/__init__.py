"""ClauseGuard configuration package."""

from clauseguard.config.settings import (
    API_KEY,
    BASE_URL,
    DEEPSEEK_API_KEY,
    MAX_CLAUSES,
    MAX_TOKENS,
    MODEL_NAME,
    TEMPERATURE,
    TIMEOUT_SECONDS,
    validate_config,
)
from clauseguard.config.prompts import (
    CLASSIFIER_SYSTEM_PROMPT,
    EXTRACTOR_SYSTEM_PROMPT,
    REPORTER_SYSTEM_PROMPT,
    RISK_SCORER_SYSTEM_PROMPT,
    TRANSLATOR_SYSTEM_PROMPT,
)
from clauseguard.config.copilot_prompts import COPILOT_SYSTEM_PROMPT

__all__ = [
    "API_KEY",
    "BASE_URL",
    "CLASSIFIER_SYSTEM_PROMPT",
    "COPILOT_SYSTEM_PROMPT",
    "DEEPSEEK_API_KEY",
    "EXTRACTOR_SYSTEM_PROMPT",
    "MAX_CLAUSES",
    "MAX_TOKENS",
    "MODEL_NAME",
    "REPORTER_SYSTEM_PROMPT",
    "RISK_SCORER_SYSTEM_PROMPT",
    "TEMPERATURE",
    "TIMEOUT_SECONDS",
    "TRANSLATOR_SYSTEM_PROMPT",
    "validate_config",
]
