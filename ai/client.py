"""Azure OpenAI client singleton with lazy initialization and graceful degradation."""

import os
import logging
import threading

logger = logging.getLogger(__name__)

_client = None
_client_lock = threading.Lock()


def get_openai_client():
    """Return a lazily-initialized AzureOpenAI client singleton.

    Returns None if env vars are missing, allowing callers to fall back gracefully.
    """
    global _client
    if _client is not None:
        return _client

    with _client_lock:
        if _client is not None:
            return _client

        endpoint = os.getenv('AZURE_OPENAI_ENDPOINT')
        api_key = os.getenv('AZURE_OPENAI_API_KEY')
        api_version = os.getenv('AZURE_OPENAI_API_VERSION', '2025-01-01-preview')

        if not endpoint or not api_key:
            logger.warning("[ai] AZURE_OPENAI_ENDPOINT or API_KEY not set; AI features disabled")
            return None

        try:
            from openai import AzureOpenAI
            _client = AzureOpenAI(
                azure_endpoint=endpoint,
                api_key=api_key,
                api_version=api_version,
            )
            logger.info("[ai] Azure OpenAI client initialized (endpoint=%s)", endpoint)
            return _client
        except Exception as e:
            logger.error("[ai] Failed to initialize Azure OpenAI client: %s", e)
            return None


def get_deployment_name() -> str:
    """Return the Azure OpenAI deployment name from env."""
    return os.getenv('AZURE_OPENAI_DEPLOYMENT', 'gpt-4o-mini')


def is_ai_available() -> bool:
    """Check whether the Azure OpenAI client can be initialized."""
    return get_openai_client() is not None
