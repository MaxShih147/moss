from abc import ABC, abstractmethod


class LLMProvider(ABC):
    """Abstract interface for LLM providers."""

    @abstractmethod
    async def chat(self, user_message: str, system_prompt: str = "") -> str:
        """Send a message and return the assistant's reply."""
        ...
