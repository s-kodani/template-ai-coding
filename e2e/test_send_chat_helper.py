"""send_chat must wait for a new assistant message, not a pre-existing one."""

from __future__ import annotations

from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

from conftest import send_chat
from playwright.sync_api import Page, expect

CHAT_WITH_WELCOME_HTML = """<!doctype html>
<div data-step-type="assistant_message">welcome</div>
<textarea id="chat-input"></textarea>
<button id="chat-submit">send</button>
<script>
document.querySelector("#chat-submit").onclick = () => {
  setTimeout(() => {
    const node = document.createElement("div");
    node.setAttribute("data-step-type", "assistant_message");
    node.textContent = "https://docs.pytest.org/en/stable/";
    document.body.appendChild(node);
  }, 400);
};
</script>
"""


def _serve(html: str) -> Iterator[str]:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:
            del format, args

        def do_GET(self) -> None:
            data = html.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    try:
        yield f"http://{host}:{port}"
    finally:
        server.shutdown()


def test_send_chat_waits_for_new_assistant_message(page: Page) -> None:
    for origin in _serve(CHAT_WITH_WELCOME_HTML):
        page.goto(origin, wait_until="domcontentloaded")
        expect(page.locator('[data-step-type="assistant_message"]')).to_have_count(1)
        reply = send_chat(page, "search_web で pytest を検索して")
        assert reply.inner_text() == "https://docs.pytest.org/en/stable/"
        expect(page.locator('[data-step-type="assistant_message"]')).to_have_count(2)
