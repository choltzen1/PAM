"""AI service layer for PeteBot LLM integration (Azure OpenAI)."""

from .client import get_openai_client, get_deployment_name, is_ai_available
from .chat import pete_chat_completion
