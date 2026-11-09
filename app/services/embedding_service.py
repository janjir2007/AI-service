from __future__ import annotations

import logging
from abc import ABC, abstractmethod

import httpx

from app.config import Settings, get_settings
from app.services.ollama_client import OllamaClient

logger = logging.getLogger(__name__)


class EmbeddingProvider(ABC):
    @abstractmethod
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError


class OpenAIEmbeddingProvider(EmbeddingProvider):
    def __init__(self, settings: Settings) -> None:
        if not settings.embedding_api_key:
            raise ValueError("EMBEDDING_API_KEY is required for openai embedding provider")
        self._model = settings.embedding_model
        self._api_key = settings.embedding_api_key
        self._dimension = settings.embedding_dimension

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        url = "https://api.openai.com/v1/embeddings"
        headers = {"Authorization": f"Bearer {self._api_key}"}
        payload = {"model": self._model, "input": texts}
        try:
            with httpx.Client(timeout=120.0) as client:
                resp = client.post(url, headers=headers, json=payload)
                resp.raise_for_status()
                data = resp.json()["data"]
        except httpx.HTTPError as exc:
            logger.error("Embedding API error: %s", exc)
            raise
        vectors = [item["embedding"] for item in sorted(data, key=lambda x: x["index"])]
        for vec in vectors:
            if len(vec) != self._dimension:
                raise ValueError(
                    f"Embedding dimension mismatch: expected {self._dimension}, got {len(vec)}"
                )
        return vectors


class OllamaEmbeddingProvider(EmbeddingProvider):
    def __init__(self, settings: Settings) -> None:
        self._model = settings.embedding_model
        self._dimension = settings.embedding_dimension
        self._client = OllamaClient(settings)

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        # Ollama accepts batches; keep batches moderate for RAM.
        batch_size = 16
        vectors: list[list[float]] = []
        for start in range(0, len(texts), batch_size):
            batch = texts[start : start + batch_size]
            part = self._client.embed(self._model, batch)
            vectors.extend(part)
        for vec in vectors:
            if len(vec) != self._dimension:
                raise ValueError(
                    f"Embedding dimension mismatch: expected {self._dimension}, got {len(vec)}. "
                    f"Set EMBEDDING_DIMENSION={len(vec)} and re-run migrations if needed."
                )
        return vectors


class MockEmbeddingProvider(EmbeddingProvider):
    def __init__(self, settings: Settings) -> None:
        self._dimension = settings.embedding_dimension

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for text in texts:
            seed = sum(ord(c) for c in text) % 997
            vec = [((seed * (i + 1)) % 1000) / 1000.0 for i in range(self._dimension)]
            out.append(vec)
        return out


def get_embedding_provider(settings: Settings | None = None) -> EmbeddingProvider:
    settings = settings or get_settings()
    provider = settings.embedding_provider.lower()
    if provider == "openai":
        return OpenAIEmbeddingProvider(settings)
    if provider == "ollama":
        return OllamaEmbeddingProvider(settings)
    if provider == "mock":
        return MockEmbeddingProvider(settings)
    raise ValueError(f"Unsupported EMBEDDING_PROVIDER: {settings.embedding_provider}")
