"""Regression checks for Web-search assertions without a model or running stack."""
from __future__ import annotations

import json

import pytest
from conftest import reply_contains_url
from playwright.sync_api import Error, Page
from test_chat_web_search import (
    OPEN_WEBUI_REPEATED_TOOL_FAILURE,
)
from test_chat_web_search import (
    test_search_web_without_api_key_reports_error as check_missing_key,
)


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        ('<a href="https://docs.pytest.org/en/stable/">こちら</a>', True),
        ("https://docs.pytest.org/en/stable/", True),
        ('<a href="javascript:void(0)">こちら</a>', False),
    ],
)
def test_reply_url_includes_link_targets(page: Page, content: str, expected: bool) -> None:
    page.set_content(f'<div class="chat-assistant">{content}</div>')
    assert reply_contains_url(page.locator(".chat-assistant")) is expected


@pytest.mark.parametrize(
    ("scenario", "error"),
    [
        ("missing-key", None),
        ("pending-persistence", None),
        ("not-called", "search_web was not called"),
        ("other-tool", "search_web was not called"),
        ("missing-output", "search_web results missing"),
        ("repeated-failure-guard", None),
        ("guard-only", "search_web results missing"),
        ("non-json-output", "search_web output is not JSON"),
        ("other-error", "unexpected search_web error"),
        ("success", "unexpected search_web error"),
        ("unavailable", "Cannot read saved chat"),
    ],
)
def test_missing_key_assertion_uses_current_tool_result(
    page: Page, scenario: str, error: str | None,
) -> None:
    tool_output = {"error": "BRAVE_SEARCH_API_KEY is not configured"}
    if scenario == "other-error":
        tool_output = {"error": "Brave Search API returned 503"}
    elif scenario == "success":
        tool_output = {"query": "pytest documentation", "results": []}
    output = [
        {"type": "function_call", "call_id": "call-1", "status": "completed",
         "name": "other_tool" if scenario == "other-tool" else "web-search_search_web"},
        {"type": "function_call_output", "call_id": "call-1", "status": "completed",
         "output": [{"type": "input_text", "text": json.dumps(tool_output)}]},
    ]
    if scenario == "missing-output":
        output = output[:1]
    elif scenario == "repeated-failure-guard":
        output.append({
            "type": "function_call_output",
            "call_id": "call-1",
            "status": "completed",
            "output": [{"type": "input_text", "text": OPEN_WEBUI_REPEATED_TOOL_FAILURE}],
        })
    elif scenario == "guard-only":
        output[1]["output"] = [{"type": "input_text", "text": OPEN_WEBUI_REPEATED_TOOL_FAILURE}]
    elif scenario == "non-json-output":
        output[1]["output"] = [{"type": "input_text", "text": "Error: upstream timeout"}]
    body = {"chat": {"history": {"messages": {
        "previous": {"role": "assistant", "done": True, "output": output},
        "current": {"role": "assistant", "done": True,
                    "output": [] if scenario == "not-called" else output},
    }}}}
    reads = 0

    def serve_chat(route) -> None:
        nonlocal reads
        reads += 1
        if scenario == "unavailable":
            route.fulfill(status=503, json={"detail": "Unavailable"})
            return
        saved = body
        if scenario == "pending-persistence" and reads == 1:
            saved = json.loads(json.dumps(body))
            saved["chat"]["history"]["messages"]["current"].update(done=False, output=[])
        route.fulfill(json=saved)

    page.route("http://web-search-test.invalid/**", lambda route: route.fulfill(body="{}"))
    page.route("**/api/v1/chats/chat-id", serve_chat)
    page.goto("http://web-search-test.invalid/c/chat-id")
    page.evaluate("localStorage.setItem('token', 'test-session')")
    page.set_content('''
        <textarea id="chat-input"></textarea>
        <button id="send-message-button" onclick="send()">Send</button>
        <script>
          function send() {
            const wrapper = document.createElement('div');
            wrapper.id = 'message-current';
            wrapper.innerHTML = '<div class="chat-assistant">'
              + '<div id="response-content-container">現在、ウェブ検索を使用できません。</div></div>';
            document.body.append(wrapper);
          }
        </script>
    ''')

    if error is None:
        check_missing_key(page, "unused", None)
    else:
        with pytest.raises(Error if scenario == "unavailable" else AssertionError, match=error):
            check_missing_key(page, "unused", None)
