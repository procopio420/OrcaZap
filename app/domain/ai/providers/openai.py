"""OpenAI provider implementation."""

import logging
import time
from typing import Optional

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

from app.domain.ai.models import LLMError, LLMRequest, LLMResponse
from app.domain.ai.providers.base import LLMProvider
from app.settings import settings

logger = logging.getLogger(__name__)


class OpenAIProvider(LLMProvider):
    """OpenAI GPT provider."""

    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o-mini"):
        """Initialize OpenAI provider.
        
        Args:
            api_key: OpenAI API key (if None, uses settings)
            model: Model name (default: gpt-4o-mini)
        """
        if OpenAI is None:
            raise ImportError("openai package not installed. Install with: pip install openai")
        
        self.api_key = api_key or getattr(settings, "openai_api_key", None)
        self.model = model
        self._client = None

    @property
    def name(self) -> str:
        return "openai"

    def is_available(self) -> bool:
        """Check if OpenAI is available."""
        return self.api_key is not None and self.api_key != ""

    def _get_client(self):
        """Get or create OpenAI client."""
        if self._client is None:
            if not self.is_available():
                raise LLMError("openai", "API key not configured")
            self._client = OpenAI(api_key=self.api_key)
        return self._client

    def call(self, request: LLMRequest) -> LLMResponse:
        """Call OpenAI API."""
        if not self.is_available():
            raise LLMError("openai", "API key not configured")

        start_time = time.time()
        
        try:
            client = self._get_client()
            
            messages = []
            if request.system_prompt:
                messages.append({"role": "system", "content": request.system_prompt})
            messages.append({"role": "user", "content": request.prompt})
            
            response = client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
            )
            
            latency_ms = (time.time() - start_time) * 1000
            
            # Extract response
            content = response.choices[0].message.content
            usage = response.usage
            
            # Estimate cost (rough estimates for gpt-4o-mini)
            # Input: $0.15 per 1M tokens, Output: $0.60 per 1M tokens
            cost = None
            if usage:
                input_cost = (usage.prompt_tokens / 1_000_000) * 0.15
                output_cost = (usage.completion_tokens / 1_000_000) * 0.60
                cost = input_cost + output_cost
            
            return LLMResponse(
                content=content,
                provider="openai",
                model=self.model,
                tokens_used=usage.total_tokens if usage else None,
                cost=cost,
                latency_ms=latency_ms,
                metadata={
                    "prompt_tokens": usage.prompt_tokens if usage else None,
                    "completion_tokens": usage.completion_tokens if usage else None,
                },
            )
        
        except Exception as e:
            logger.error(f"OpenAI API error: {e}", exc_info=True)
            raise LLMError("openai", str(e), original_error=e)


