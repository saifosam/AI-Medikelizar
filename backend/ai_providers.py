"""
AI-Medikelizar — AI Provider Abstraction
=========================================
Unified interface for calling different LLM providers.

Each provider implements:
    async def complete(prompt: str, system_prompt: str) -> str

Supported: OpenAI, Ollama, Anthropic, Google Gemini, Custom (OpenAI-compatible)
"""

import json
from abc import ABC, abstractmethod
from typing import Optional

import httpx

from . import config


class AIProviderError(Exception):
    """Raised when the AI provider returns an error."""
    pass


class BaseProvider(ABC):
    """Abstract base for all AI providers."""

    @abstractmethod
    async def complete(self, prompt: str, system_prompt: str) -> str:
        """Send prompt to the model and return the text response."""
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name, e.g. 'openai', 'ollama'."""
        ...

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Current model identifier."""
        ...


# ── OpenAI ─────────────────────────────────────────────

class OpenAIProvider(BaseProvider):
    def __init__(self):
        if not config.OPENAI_API_KEY:
            raise AIProviderError(
                "OpenAI API key is not configured. "
                "Set it in js/config.js or the OPENAI_API_KEY env var."
            )

    @property
    def name(self) -> str:
        return "openai"

    @property
    def model_name(self) -> str:
        return config.OPENAI_MODEL

    async def complete(self, prompt: str, system_prompt: str) -> str:
        endpoint = f"{config.OPENAI_ENDPOINT.rstrip('/')}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {config.OPENAI_API_KEY}",
        }
        body = {
            "model": config.OPENAI_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.3,
            "max_tokens": 2048,
        }

        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(endpoint, json=body, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError):
            raise AIProviderError(f"Unexpected OpenAI response: {data}")


# ── Ollama ─────────────────────────────────────────────

class OllamaProvider(BaseProvider):
    def __init__(self):
        self.base_url = config.OLLAMA_BASE_URL.rstrip("/")

    @property
    def name(self) -> str:
        return "ollama"

    @property
    def model_name(self) -> str:
        return config.OLLAMA_MODEL

    async def complete(self, prompt: str, system_prompt: str) -> str:
        endpoint = f"{self.base_url}/api/chat"
        body = {
            "model": config.OLLAMA_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            "stream": False,
            "options": {"temperature": 0.3},
        }

        async with httpx.AsyncClient(timeout=120) as client:
            try:
                resp = await client.post(endpoint, json=body)
                resp.raise_for_status()
                data = resp.json()
            except (httpx.ConnectError, httpx.TimeoutException) as e:
                raise AIProviderError(
                    f"Cannot connect to Ollama at {self.base_url}. "
                    f"Ensure Ollama is running. Details: {e}"
                )

        try:
            return data["message"]["content"]
        except (KeyError, TypeError):
            raise AIProviderError(f"Unexpected Ollama response: {data}")


# ── Anthropic ──────────────────────────────────────────

class AnthropicProvider(BaseProvider):
    def __init__(self):
        if not config.ANTHROPIC_API_KEY:
            raise AIProviderError(
                "Anthropic API key is not configured. "
                "Set it in js/config.js or the ANTHROPIC_API_KEY env var."
            )

    @property
    def name(self) -> str:
        return "anthropic"

    @property
    def model_name(self) -> str:
        return config.ANTHROPIC_MODEL

    async def complete(self, prompt: str, system_prompt: str) -> str:
        endpoint = "https://api.anthropic.com/v1/messages"
        headers = {
            "Content-Type": "application/json",
            "x-api-key": config.ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
        }
        body = {
            "model": config.ANTHROPIC_MODEL,
            "system": system_prompt,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 2048,
            "temperature": 0.3,
        }

        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(endpoint, json=body, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        try:
            return data["content"][0]["text"]
        except (KeyError, IndexError):
            raise AIProviderError(f"Unexpected Anthropic response: {data}")


# ── Google Gemini ──────────────────────────────────────

class GoogleProvider(BaseProvider):
    def __init__(self):
        if not config.GOOGLE_API_KEY:
            raise AIProviderError(
                "Google AI API key is not configured. "
                "Set it in js/config.js or the GOOGLE_API_KEY env var."
            )

    @property
    def name(self) -> str:
        return "google"

    @property
    def model_name(self) -> str:
        return config.GOOGLE_MODEL

    async def complete(self, prompt: str, system_prompt: str) -> str:
        model = config.GOOGLE_MODEL
        url = (f"https://generativelanguage.googleapis.com/v1beta/"
               f"models/{model}:generateContent"
               f"?key={config.GOOGLE_API_KEY}")
        headers = {"Content-Type": "application/json"}
        body = {
            "contents": [{
                "parts": [
                    {"text": f"{system_prompt}\n\n{prompt}"}
                ]
            }],
            "generationConfig": {
                "temperature": 0.3,
                "maxOutputTokens": 2048,
            }
        }

        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(url, json=body, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        try:
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError):
            raise AIProviderError(f"Unexpected Google response: {data}")


# ── Custom (OpenAI-compatible) ────────────────────────

class CustomProvider(BaseProvider):
    def __init__(self):
        if not config.CUSTOM_ENDPOINT:
            raise AIProviderError(
                "Custom endpoint URL is not configured. "
                "Set it in js/config.js or the CUSTOM_ENDPOINT env var."
            )
        self.endpoint = config.CUSTOM_ENDPOINT.rstrip("/")

    @property
    def name(self) -> str:
        return "custom"

    @property
    def model_name(self) -> str:
        return config.CUSTOM_MODEL or "custom"

    async def complete(self, prompt: str, system_prompt: str) -> str:
        headers = {"Content-Type": "application/json"}
        if config.CUSTOM_API_KEY:
            headers["Authorization"] = f"Bearer {config.CUSTOM_API_KEY}"

        body = {
            "model": config.CUSTOM_MODEL or "default",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.3,
            "max_tokens": 2048,
        }

        async with httpx.AsyncClient(timeout=120) as client:
            try:
                resp = await client.post(self.endpoint, json=body,
                                          headers=headers)
                resp.raise_for_status()
                data = resp.json()
            except httpx.ConnectError as e:
                raise AIProviderError(
                    f"Cannot connect to custom endpoint at {self.endpoint}. "
                    f"Details: {e}"
                )

        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError):
            raise AIProviderError(f"Unexpected custom endpoint response: {data}")


# ── Factory ────────────────────────────────────────────

_PROVIDERS = {
    "openai": OpenAIProvider,
    "ollama": OllamaProvider,
    "anthropic": AnthropicProvider,
    "google": GoogleProvider,
    "custom": CustomProvider,
}


def get_provider() -> BaseProvider:
    """Factory: return the provider instance for the active config."""
    provider_name = config.PROVIDER
    cls = _PROVIDERS.get(provider_name)
    if cls is None:
        raise AIProviderError(
            f"Unknown provider '{provider_name}'. "
            f"Valid options: {', '.join(_PROVIDERS.keys())}"
        )
    return cls()
