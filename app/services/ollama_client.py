from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import Settings

logger = logging.getLogger(__name__)


class OllamaClient:
    def __init__(self, settings: Settings) -> None:
        base = settings.ollama_base_url.rstrip("/")
        self._base = base
        self._chat_timeout = settings.ollama_chat_timeout
        self._embed_timeout = settings.ollama_embed_timeout
        self._num_ctx = settings.ollama_num_ctx
        self._num_predict = settings.ollama_num_predict
        self._repeat_penalty = settings.ollama_repeat_penalty
        self._think = settings.ollama_think.strip().lower()

    def chat(
        self,
        model: str,
        messages: list[dict[str, str]],
        temperature: float = 0.1,
        format: Any = None,
    ) -> str:
        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": self._num_predict,
                "num_ctx": self._num_ctx,
                "repeat_penalty": self._repeat_penalty,
            },
        }
        if format is not None:
            payload["format"] = format
        if self._think in ("true", "false"):
            payload["think"] = self._think == "true"
        data = self._post_json("/api/chat", payload, timeout=self._chat_timeout)
        # Durations from Ollama are in nanoseconds.
        logger.info(
            "Ollama chat: num_ctx=%s prompt_tokens=%s answer_tokens=%s "
            "load=%.1fs prompt=%.1fs answer=%.1fs total=%.1fs",
            self._num_ctx,
            data.get("prompt_eval_count"),
            data.get("eval_count"),
            data.get("load_duration", 0) / 1e9,
            data.get("prompt_eval_duration", 0) / 1e9,
            data.get("eval_duration", 0) / 1e9,
            data.get("total_duration", 0) / 1e9,
        )
        if data.get("eval_count") and data["eval_count"] >= self._num_predict:
            logger.warning(
                "Ollama answer hit num_predict=%s (cut off; possible repetition loop)",
                self._num_predict,
            )
        return data["message"]["content"].strip()

    def embed(self, model: str, inputs: list[str]) -> list[list[float]]:
        if not inputs:
            return []
        payload: dict[str, Any] = {"model": model, "input": inputs if len(inputs) > 1 else inputs[0]}
        try:
            data = self._post_json("/api/embed", payload, timeout=self._embed_timeout)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code != 404:
                raise
            logger.warning("Ollama /api/embed not found; falling back to /api/embeddings (upgrade Ollama when possible)")
            return self._embed_legacy(model, inputs)
        embeddings = data.get("embeddings")
        if embeddings is None:
            one = data.get("embedding")
            if one is not None:
                return [one]
            raise ValueError("Ollama embed response missing embeddings")
        return embeddings

    def _embed_legacy(self, model: str, inputs: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in inputs:
            data = self._post_json(
                "/api/embeddings",
                {"model": model, "prompt": text},
                timeout=self._embed_timeout,
            )
            vec = data.get("embedding")
            if vec is None:
                raise ValueError("Ollama /api/embeddings response missing embedding")
            vectors.append(vec)
        return vectors

    def _post_json(self, path: str, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
        url = f"{self._base}{path}"
        try:
            with httpx.Client(timeout=timeout) as client:
                resp = client.post(url, json=payload)
                resp.raise_for_status()
                return resp.json()
        except httpx.ConnectError as exc:
            raise ConnectionError(
                f"Cannot reach Ollama at {self._base}. Install Ollama and run: ollama serve"
            ) from exc
        except httpx.HTTPStatusError as exc:
            if path == "/api/embed" and exc.response.status_code == 404:
                raise
            body = exc.response.text[:200] if exc.response is not None else ""
            if exc.response.status_code == 404:
                raise RuntimeError(
                    f"Ollama model or route not found at {url}. "
                    f"Run: ollama pull {payload.get('model', 'nomic-embed-text')} "
                    f"and ensure `ollama serve` is running. {body}"
                ) from exc
            logger.error("Ollama request failed %s: %s", path, exc)
            raise
        except httpx.HTTPError as exc:
            logger.error("Ollama request failed %s: %s", path, exc)
            raise
