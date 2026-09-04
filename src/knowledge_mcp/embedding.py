from __future__ import annotations

import httpx

from knowledge_mcp.config import Settings


class EmbeddingError(Exception):
    """Embedding provider failed."""


class EmbeddingClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = httpx.AsyncClient(
            base_url=settings.openai_base_url.rstrip("/"),
            headers={"Authorization": f"Bearer {settings.openai_api_key}"},
            timeout=settings.embedding_timeout,
        )

    @property
    def model(self) -> str:
        return self._settings.embedding_model

    @property
    def dimensions(self) -> int:
        return self._settings.embedding_dimensions

    async def embed(self, text: str) -> tuple[list[float], dict[str, int] | None]:
        if not self._settings.openai_api_key:
            raise EmbeddingError(
                "Embedding API key is not configured. Set OPENAI_API_KEY before searching."
            )
        response = await self._client.post(
            "/embeddings",
            json={
                "model": self._settings.embedding_model,
                "input": text,
                "dimensions": self._settings.embedding_dimensions,
            },
        )
        if response.status_code >= 400:
            raise EmbeddingError(
                f"Embedding request failed with status {response.status_code}. "
                "Check OPENAI_API_KEY and OPENAI_BASE_URL."
            )
        payload = response.json()
        try:
            vector = payload["data"][0]["embedding"]
        except (KeyError, IndexError, TypeError) as exc:
            raise EmbeddingError("Embedding response did not include a vector.") from exc
        if len(vector) != self._settings.embedding_dimensions:
            raise EmbeddingError(
                f"Embedding dimension mismatch: expected {self._settings.embedding_dimensions}, "
                f"got {len(vector)}."
            )
        usage_payload = payload.get("usage")
        usage: dict[str, int] | None = None
        if isinstance(usage_payload, dict):
            total = usage_payload.get("total_tokens")
            if total is not None:
                usage = {"total": int(total)}
        return vector, usage

    async def aclose(self) -> None:
        await self._client.aclose()
