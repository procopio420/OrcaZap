"""AI request/response models."""

from typing import Any, Optional
from uuid import UUID


class LLMRequest:
    """LLM request model."""

    def __init__(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        tenant_id: Optional[UUID] = None,
    ):
        self.prompt = prompt
        self.system_prompt = system_prompt
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.tenant_id = tenant_id


class LLMResponse:
    """LLM response model."""

    def __init__(
        self,
        content: str,
        provider: str,
        model: str,
        tokens_used: Optional[int] = None,
        cost: Optional[float] = None,
        latency_ms: Optional[float] = None,
        metadata: Optional[dict[str, Any]] = None,
    ):
        self.content = content
        self.provider = provider
        self.model = model
        self.tokens_used = tokens_used
        self.cost = cost
        self.latency_ms = latency_ms
        self.metadata = metadata or {}


class LLMError(Exception):
    """LLM provider error."""

    def __init__(self, provider: str, message: str, original_error: Optional[Exception] = None):
        self.provider = provider
        self.message = message
        self.original_error = original_error
        super().__init__(f"{provider}: {message}")


