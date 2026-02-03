"""Anthropic Claude provider implementation."""

import logging
import time
from typing import Optional

try:
    from anthropic import Anthropic
except ImportError:
    Anthropic = None

from app.domain.ai.models import LLMError, LLMRequest, LLMResponse
from app.domain.ai.providers.base import LLMProvider
from app.settings import settings

logger = logging.getLogger(__name__)


class AnthropicProvider(LLMProvider):
    """Anthropic Claude provider."""

    def __init__(self, api_key: Optional[str] = None, model: str = "claude-3-haiku-20240307"):
        """Initialize Anthropic provider.
        
        Args:
            api_key: Anthropic API key (if None, uses settings)
            model: Model name (default: claude-3-haiku-20240307)
        """
        if Anthropic is None:
            raise ImportError("anthropic package not installed. Install with: pip install anthropic")
        
        self.api_key = api_key or getattr(settings, "anthropic_api_key", None)
        self.model = model
        self._client = None

    @property
    def name(self) -> str:
        return "anthropic"

    def is_available(self) -> bool:
        """Check if Anthropic is available."""
        return self.api_key is not None and self.api_key != ""

    def _get_client(self):
        """Get or create Anthropic client."""
        if self._client is None:
            if not self.is_available():
                raise LLMError("anthropic", "API key not configured")
            self._client = Anthropic(api_key=self.api_key)
        return self._client

    def call(self, request: LLMRequest) -> LLMResponse:
        """Call Anthropic API."""
        if not self.is_available():
            raise LLMError("anthropic", "API key not configured")

        start_time = time.time()
        
        try:
            client = self._get_client()
            
            # Build messages
            system = request.system_prompt or ""
            messages = [{"role": "user", "content": request.prompt}]
            
            response = client.messages.create(
                model=self.model,
                max_tokens=request.max_tokens or 1024,
                temperature=request.temperature,
                system=system if system else None,
                messages=messages,
            )
            
            latency_ms = (time.time() - start_time) * 1000
            
            # Extract response
            content = response.content[0].text if response.content else ""
            usage = response.usage
            
            # Estimate cost (rough estimates for claude-3-haiku)
            # Input: $0.25 per 1M tokens, Output: $1.25 per 1M tokens
            cost = None
            if usage:
                input_cost = (usage.input_tokens / 1_000_000) * 0.25
                output_cost = (usage.output_tokens / 1_000_000) * 1.25
                cost = input_cost + output_cost
            
            return LLMResponse(
                content=content,
                provider="anthropic",
                model=self.model,
                tokens_used=usage.input_tokens + usage.output_tokens if usage else None,
                cost=cost,
                latency_ms=latency_ms,
                metadata={
                    "input_tokens": usage.input_tokens if usage else None,
                    "output_tokens": usage.output_tokens if usage else None,
                },
            )
        
        except Exception as e:
            logger.error(f"Anthropic API error: {e}", exc_info=True)
            raise LLMError("anthropic", str(e), original_error=e)

