"""LLM router with fallback support."""

import logging
from typing import Optional
from uuid import UUID

from app.domain.ai.config import get_provider_config
from app.domain.ai.models import LLMError, LLMRequest, LLMResponse
from app.domain.ai.providers import AnthropicProvider, OpenAIProvider
from app.domain.ai.providers.base import LLMProvider

logger = logging.getLogger(__name__)


class LLMRouter:
    """Router for LLM providers with fallback support."""

    def __init__(self):
        """Initialize router with available providers."""
        self.providers: dict[str, LLMProvider] = {}
        
        # Initialize OpenAI
        try:
            openai_provider = OpenAIProvider()
            if openai_provider.is_available():
                self.providers["openai"] = openai_provider
                logger.info("OpenAI provider initialized")
        except Exception as e:
            logger.warning(f"OpenAI provider not available: {e}")
        
        # Initialize Anthropic
        try:
            anthropic_provider = AnthropicProvider()
            if anthropic_provider.is_available():
                self.providers["anthropic"] = anthropic_provider
                logger.info("Anthropic provider initialized")
        except Exception as e:
            logger.warning(f"Anthropic provider not available: {e}")
        
        if not self.providers:
            logger.warning("No LLM providers available")

    def call(
        self,
        request: LLMRequest,
        tenant_id: Optional[UUID] = None,
        preferred_provider: Optional[str] = None,
    ) -> LLMResponse:
        """Call LLM with fallback support.
        
        Args:
            request: LLM request
            tenant_id: Optional tenant ID for tenant-specific config
            preferred_provider: Optional preferred provider name (overrides config)
        
        Returns:
            LLM response from first available provider
        
        Raises:
            LLMError: If all providers fail
        """
        if not self.providers:
            raise LLMError("router", "No LLM providers available")
        
        # Get provider order from config
        config = get_provider_config(tenant_id)
        primary = preferred_provider or config.get("primary", "openai")
        fallback = config.get("fallback", "anthropic")
        
        # Try providers in order: preferred -> primary -> fallback -> any available
        providers_to_try = []
        if preferred_provider and preferred_provider in self.providers:
            providers_to_try.append(preferred_provider)
        if primary not in providers_to_try and primary in self.providers:
            providers_to_try.append(primary)
        if fallback not in providers_to_try and fallback in self.providers:
            providers_to_try.append(fallback)
        # Add any other available providers
        for provider_name in self.providers:
            if provider_name not in providers_to_try:
                providers_to_try.append(provider_name)
        
        last_error = None
        for provider_name in providers_to_try:
            provider = self.providers[provider_name]
            try:
                logger.info(f"Trying LLM provider: {provider_name}")
                response = provider.call(request)
                logger.info(f"LLM call successful with {provider_name} (latency: {response.latency_ms:.0f}ms)")
                return response
            except LLMError as e:
                logger.warning(f"LLM provider {provider_name} failed: {e.message}")
                last_error = e
                continue
            except Exception as e:
                logger.error(f"Unexpected error with provider {provider_name}: {e}", exc_info=True)
                last_error = LLMError(provider_name, str(e), original_error=e)
                continue
        
        # All providers failed
        raise LLMError(
            "router",
            f"All LLM providers failed. Last error: {last_error.message if last_error else 'Unknown'}",
            original_error=last_error,
        )


# Global router instance
_router: Optional[LLMRouter] = None


def get_llm_router() -> LLMRouter:
    """Get global LLM router instance."""
    global _router
    if _router is None:
        _router = LLMRouter()
    return _router


