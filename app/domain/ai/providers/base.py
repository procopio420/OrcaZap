"""Base LLM provider interface."""

from abc import ABC, abstractmethod

from app.domain.ai.models import LLMRequest, LLMResponse


class LLMProvider(ABC):
    """Base interface for LLM providers."""

    @abstractmethod
    def call(self, request: LLMRequest) -> LLMResponse:
        """Call the LLM provider.
        
        Args:
            request: LLM request with prompt and parameters
        
        Returns:
            LLM response with content and metadata
        
        Raises:
            LLMError: If the provider call fails
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if provider is available (API key configured).
        
        Returns:
            True if provider is available, False otherwise
        """
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name."""
        pass








