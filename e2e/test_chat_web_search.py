"""Web search e2e: dev2 uses search_web via Gateway MCP."""

from __future__ import annotations

import json
from urllib.parse import urlsplit

import pytest
from conftest import reply_contains_url, send_chat
from playwright.sync_api import Locator, Page

pytestmark = pytest.mark.e2e_brave

# Open WebUI v0.13.1 backend/open_webui/utils/tool_calling.py tool_repetition_error
OPEN_WEBUI_REPEATED_TOOL_FAILURE = (
    "Error: the same tool call failed twice. Finish using the available results."
)

SEARCH_WEB_PROMPT = (
    "search_web ツールで「pytest documentation」を検索し、"
    "見つかった公式ドキュメントの URL を1つだけ答えてください。"
)


def test_dev2_search_web_returns_url(
    logged_in_dev2: Page,
    openai_api_key: str,
    brave_search_api_key: str,
) -> None:
    del openai_api_key, brave_search_api_key

    reply = send_chat(logged_in_dev2, SEARCH_WEB_PROMPT)
    results = _search_web_results(logged_in_dev2, reply)
    assert any(result.get("results") for result in results), "search_web returned no web results"
    text = reply.inner_text()
    assert reply_contains_url(reply), f"assistant reply had no URL: {text!r}"


def test_search_web_without_api_key_reports_error(
    logged_in_dev2: Page,
    openai_api_key: str,
    require_empty_brave_search_api_key: None,
) -> None:
    del openai_api_key, require_empty_brave_search_api_key

    reply = send_chat(logged_in_dev2, SEARCH_WEB_PROMPT)
    results = _search_web_results(logged_in_dev2, reply)
    assert all(result.get("error") == "BRAVE_SEARCH_API_KEY is not configured" for result in results), (
        "unexpected search_web error: expected missing BRAVE_SEARCH_API_KEY"
    )


def _search_web_results(page: Page, reply: Locator) -> list[dict]:
    chat_id = urlsplit(page.url).path.removeprefix("/c/")
    message_id = reply.evaluate(
        '''element => element.closest('[id^="message-"]').id.slice('message-'.length)'''
    )
    # Stop disappearing precedes persistence. Poll this exact reply's saved output,
    # not the model's paraphrase or an earlier message's successful tool call.
    output = page.evaluate('''async ({chatId, messageId}) => {
        const signal = AbortSignal.timeout(10000);
        while (!signal.aborted) {
            const response = await fetch(`/api/v1/chats/${encodeURIComponent(chatId)}`, {
                headers: {Authorization: `Bearer ${localStorage.token}`}, signal
            });
            if (!response.ok) throw new Error(`Cannot read saved chat (${response.status})`);
            const data = await response.json();
            const message = data.chat?.history?.messages?.[messageId];
            if (message?.done) return message.output ?? [];
            await new Promise(resolve => setTimeout(resolve, 100));
        }
        throw new Error('This reply was not persisted');
    }''', {"chatId": chat_id, "messageId": message_id})
    call_ids = {
        item["call_id"] for item in output
        if item.get("type") == "function_call" and item.get("name") == "web-search_search_web"
    }
    assert call_ids, "search_web was not called in this reply"
    results = []
    for item in output:
        if item.get("type") != "function_call_output" or item.get("call_id") not in call_ids:
            continue
        text = "".join(part.get("text", "") for part in item.get("output", []))
        if text == OPEN_WEBUI_REPEATED_TOOL_FAILURE:
            continue
        try:
            results.append(json.loads(text))
        except json.JSONDecodeError:
            raise AssertionError(f"search_web output is not JSON: {text!r}") from None
    assert results, "search_web results missing from this reply"
    return results
