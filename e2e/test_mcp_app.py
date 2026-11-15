"""Real Host smoke: server pagination and chunk details through Open WebUI MCP Apps."""
from __future__ import annotations

import re
from collections.abc import Callable

from conftest import send_chat
from playwright.sync_api import Error, Page, expect


def test_streaming_text_does_not_repeatedly_reload_the_same_mcp_app(
    logged_in_dev: Page,
    openai_api_key: str,
) -> None:
    del openai_api_key
    page = logged_in_dev
    # Establish a saved chat before observing Apps, avoiding the initial route transition.
    send_chat(page, "ツールは使わず、「準備完了」とだけ回答してください。")
    # A binding identifies a server/tool, not an App instance. Each new iframe
    # needs its own initial resource, including Apps in earlier messages.
    mounts = page.evaluate_handle('''() => {
        const selector = 'iframe[title="search_knowledge"]';
        const seen = new Set(document.querySelectorAll(selector));
        let count = 0;
        const observer = new MutationObserver(records => {
            for (const record of records) {
                for (const node of record.addedNodes) {
                    if (!(node instanceof Element)) continue;
                    const frames = [...node.querySelectorAll(selector)];
                    if (node.matches(selector)) frames.push(node);
                    for (const frame of frames) {
                        if (!seen.has(frame)) { seen.add(frame); count++; }
                    }
                }
            }
        });
        observer.observe(document.body, {childList: true, subtree: true});
        return {get count() { return count; }};
    }''')
    resource_requests = 0

    def record_resource(request) -> None:
        nonlocal resource_requests
        if "/mcp/app/rpc" in request.url and request.method == "POST":
            body = request.post_data_json
            if body.get("method") == "ui/resource" and body.get("tool_name") == "search_knowledge":
                resource_requests += 1

    page.on("request", record_resource)
    replies = page.locator(".chat-assistant")
    before = replies.count()
    page.locator("#chat-input").fill(
        "search_knowledge を query='Architecture Overview', top_k=1, offset=0 で1回だけ実行し、"
        "検索結果を表示してください。他のツールは使わないでください。"
        "検索後に、取得した結果をもとにシステムの構成を日本語の長い文章で30文説明してください。"
    )
    page.locator("#send-message-button").click()
    expect(replies).to_have_count(before + 1, timeout=120_000)
    reply = replies.last
    frame = reply.locator('iframe[title="search_knowledge"]').first
    expect(frame).to_have_count(1, timeout=60_000)
    expect(frame).to_be_visible(timeout=60_000)
    app = reply.frame_locator('iframe[title="search_knowledge"]').first
    expect(app.locator("#results > li")).to_have_count(1, timeout=60_000)
    original = frame.element_handle()
    assert original is not None
    original_document = app.locator("html").element_handle()
    assert original_document is not None

    def assert_stable() -> None:
        assert reply.evaluate(
            "(reply, original) => reply.contains(original)"
            " && original.isConnected && !original.closest('[inert]')",
            original,
        ), "Streaming remounted or deactivated the App"
        try:
            document_connected = original_document.evaluate("element => element.isConnected")
        except Error:
            # Navigation destroys the old document's JavaScript context.
            document_connected = False
        assert document_connected, "Streaming reloaded the App document"
        mount_count = mounts.evaluate("state => state.count")
        assert resource_requests <= mount_count, (
            "Streaming re-fetched the App resource without mounting a new App"
        )

    stop = page.get_by_role("button", name=re.compile(r"^(Stop|停止)$"))
    expect(stop).to_be_visible()
    # Require text updates after the App appears; a completed reply cannot cover this regression.
    for _ in range(3):
        initial_text = reply.inner_text()
        expect(reply).not_to_have_text(initial_text, timeout=30_000)
        expect(stop).to_be_visible()
        assert_stable()
    expect(stop).not_to_be_visible(timeout=120_000)
    assert_stable()


def _app_call(page: Page, action: Callable[[], object], tool_name: str) -> dict:
    action()
    dialog = page.get_by_role("dialog", name=re.compile("Tool call|ツール呼び出し", re.IGNORECASE))
    expect(dialog).to_be_visible(timeout=15_000)
    expect(dialog).to_contain_text(tool_name)

    def is_tool_response(response) -> bool:
        if "/mcp/app/rpc" not in response.url or response.request.method != "POST":
            return False
        body = response.request.post_data_json
        return body.get("method") == "tools/call" and body.get("params", {}).get("name") == tool_name

    with page.expect_response(is_tool_response, timeout=90_000) as response_info:
        dialog.get_by_role("button", name=re.compile(r"^(Confirm|確認|承認)$")).click()
    response = response_info.value
    assert response.ok, "App tool request failed"
    result = response.json()
    assert not result.get("isError"), "MCP tool returned an error"
    return result["structuredContent"]


def test_mcp_app_shows_chunk_detail_and_pages_on_the_server(
    logged_in_dev: Page,
    openai_api_key: str,
) -> None:
    del openai_api_key
    page = logged_in_dev
    send_chat(
        page,
        "search_knowledge を query='Architecture Overview', top_k=1, offset=0 で1回実行し、"
        "検索結果を表示してください。get_document は実行しないでください。",
    )
    app = page.frame_locator('iframe[title="search_knowledge"]').last
    results = app.locator("#results > li")
    expect(results).to_have_count(1, timeout=60_000)
    expect(app.locator("#range")).to_contain_text("1–1件")
    expect(app.get_by_role("button", name="‹ 前へ", exact=True)).to_be_disabled()

    first = app.locator(".title").first
    document_id = first.get_attribute("data-document-id")
    detail = _app_call(page, first.click, "get_document")
    assert detail["document_id"] == document_id
    expect(app.locator(".detail-body")).to_have_text(detail["content"], timeout=30_000)

    second_page = _app_call(
        page,
        app.get_by_role("button", name="次へ ›", exact=True).click,
        "search_knowledge",
    )
    assert second_page["pagination"]["offset"] == 1
    expect(app.locator("#range")).to_contain_text("2–2件", timeout=30_000)
    expect(app.locator(".detail-empty")).to_contain_text("文書を選ぶと")

    first_page = _app_call(
        page,
        app.get_by_role("button", name="‹ 前へ", exact=True).click,
        "search_knowledge",
    )
    assert first_page["pagination"]["offset"] == 0
    expect(app.locator("#page-label")).to_have_text("1ページ目", timeout=30_000)

    for page_size in (20, 5, 10):
        result = _app_call(
            page,
            lambda value=page_size: app.get_by_role("combobox", name="1ページの表示件数")
            .select_option(str(value)),
            "search_knowledge",
        )
        assert result["pagination"]["offset"] == 0
        assert result["pagination"]["page_size"] == page_size
        expect(results).to_have_count(len(result["hits"]), timeout=30_000)
        expect(app.locator("#page-label")).to_have_text("1ページ目")
        if not result["pagination"]["has_more"]:
            expect(app.get_by_role("button", name="次へ ›", exact=True)).to_be_disabled()
