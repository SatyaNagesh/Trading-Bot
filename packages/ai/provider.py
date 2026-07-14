"""AI Provider Abstraction — multi-model orchestrator with provider-agnostic interface."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from packages.core.logging import get_logger
from packages.core.config import settings

logger = get_logger("ai_provider")


@dataclass
class AIResponse:
    content: str
    model: str
    provider: str
    usage: dict[str, int] = field(default_factory=dict)
    raw: dict[str, Any] | None = None


class AIProvider(ABC):
    def __init__(self, api_key: str, model: str = "default"):
        self.api_key = api_key
        self.model = model

    @abstractmethod
    async def complete(self, prompt: str, **kwargs: Any) -> AIResponse:
        ...

    @abstractmethod
    async def chat(self, messages: list[dict[str, str]], **kwargs: Any) -> AIResponse:
        ...


class OpenAIProvider(AIProvider):
    async def complete(self, prompt: str, **kwargs: Any) -> AIResponse:
        raise NotImplementedError("OpenAI integration pending")

    async def chat(self, messages: list[dict[str, str]], **kwargs: Any) -> AIResponse:
        raise NotImplementedError("OpenAI integration pending")


class AnthropicProvider(AIProvider):
    async def complete(self, prompt: str, **kwargs: Any) -> AIResponse:
        raise NotImplementedError("Anthropic integration pending")

    async def chat(self, messages: list[dict[str, str]], **kwargs: Any) -> AIResponse:
        raise NotImplementedError("Anthropic integration pending")


class OllamaProvider(AIProvider):
    def __init__(self, api_key: str = "", model: str = "llama3.2:1b", base_url: str = "http://localhost:11434"):
        super().__init__(api_key, model)
        self.base_url = base_url

    async def complete(self, prompt: str, **kwargs: Any) -> AIResponse:
        import httpx
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.base_url}/api/generate",
                json={"model": self.model, "prompt": prompt},
                timeout=120,
            )
            data = resp.json()
            return AIResponse(
                content=data.get("response", ""),
                model=self.model,
                provider="ollama",
            )

    async def chat(self, messages: list[dict[str, str]], **kwargs: Any) -> AIResponse:
        import httpx
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.base_url}/api/chat",
                json={"model": self.model, "messages": messages},
                timeout=120,
            )
            data = resp.json()
            return AIResponse(
                content=data.get("message", {}).get("content", ""),
                model=self.model,
                provider="ollama",
            )


class OpenRouterProvider(AIProvider):
    async def complete(self, prompt: str, **kwargs: Any) -> AIResponse:
        raise NotImplementedError("OpenRouter integration pending")

    async def chat(self, messages: list[dict[str, str]], **kwargs: Any) -> AIResponse:
        raise NotImplementedError("OpenRouter integration pending")


class AIOrchestrator:
    def __init__(self):
        self.providers: dict[str, AIProvider] = {}
        self._init_providers()

    def _init_providers(self):
        if settings.OPENAI_API_KEY:
            self.providers["openai"] = OpenAIProvider(settings.OPENAI_API_KEY)
        if settings.ANTHROPIC_API_KEY:
            self.providers["anthropic"] = AnthropicProvider(settings.ANTHROPIC_API_KEY)
        self.providers["ollama"] = OllamaProvider()

    def get_provider(self, name: str = "ollama") -> AIProvider:
        provider = self.providers.get(name)
        if not provider:
            raise ValueError(f"Unavailable provider: {name}")
        return provider
