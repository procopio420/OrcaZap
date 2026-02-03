"""LLM provider configuration."""

from typing import Optional
from uuid import UUID

from app.settings import settings


def get_provider_config(tenant_id: Optional[UUID] = None) -> dict[str, str]:
    """Get provider configuration for tenant or global.
    
    Args:
        tenant_id: Optional tenant ID for tenant-specific config
    
    Returns:
        Dict with provider preferences (e.g., {"primary": "openai", "fallback": "anthropic"})
    """
    # For now, use global config from settings
    # In the future, can be tenant-specific
    primary = getattr(settings, "llm_primary_provider", "openai")
    fallback = getattr(settings, "llm_fallback_provider", "anthropic")
    
    return {
        "primary": primary,
        "fallback": fallback,
    }


