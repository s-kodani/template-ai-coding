from __future__ import annotations

from typing import Any

import httpx
from pydantic import BaseModel, Field


class WebSearchHit(BaseModel):
    title: str
    url: str
    snippet: str = ""


class WebSearchResult(BaseModel):
    query: str
    results: list[WebSearchHit] = Field(default_factory=list)


class BraveSearchClient:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        timeout: float,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._api_key = api_key.strip()
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._client = client

    async def search_web(self, *, query: str, count: int = 5) -> WebSearchResult:
        cleaned = query.strip()
        if not cleaned:
            raise ValueError("query must not be empty")
        if not self._api_key:
            raise ValueError("BRAVE_SEARCH_API_KEY is not configured")
        if count < 1 or count > 20:
            raise ValueError("count must be between 1 and 20")

        own_client = self._client is None
        client = self._client or httpx.AsyncClient(timeout=self._timeout)
        try:
            response = await client.get(
                self._base_url,
                params={"q": cleaned, "count": count},
                headers={
                    "Accept": "application/json",
                    "Accept-Encoding": "gzip",
                    "X-Subscription-Token": self._api_key,
                },
            )
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPStatusError as exc:
            raise ValueError(f"Brave Search API returned {exc.response.status_code}") from exc
        except httpx.HTTPError as exc:
            raise ValueError("Brave Search API request failed") from exc
        finally:
            if own_client:
                await client.aclose()

        hits = _parse_hits(payload, limit=count)
        return WebSearchResult(query=cleaned, results=hits)


def _parse_hits(payload: dict[str, Any], *, limit: int) -> list[WebSearchHit]:
    web = payload.get("web") or {}
    raw_results = web.get("results") or []
    hits: list[WebSearchHit] = []
    for item in raw_results:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        url = str(item.get("url") or "").strip()
        if not title or not url:
            continue
        hits.append(
            WebSearchHit(
                title=title,
                url=url,
                snippet=str(item.get("description") or item.get("snippet") or "").strip(),
            )
        )
        if len(hits) >= limit:
            break
    return hits
