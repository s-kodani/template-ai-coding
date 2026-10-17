"""login_keycloak must wait for a delayed Keycloak form (no compose stack)."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

import pytest
from conftest import login_keycloak
from playwright.sync_api import Page, expect

CHAT_HTML = """<!doctype html>
<textarea id="chat-input"></textarea>
"""

LOGIN_HTML = """<!doctype html>
<button>Continue with Keycloak</button>
<script>
document.querySelector("button").onclick = () => { location.href = "/auth"; };
</script>
"""

DELAYED_AUTH_HTML = """<!doctype html>
<body>
<script>
setTimeout(() => {
  document.body.innerHTML = `
    <input id="username">
    <input id="password" type="password">
    <button type="button" id="kc-login">Sign In</button>
  `;
  document.querySelector("#kc-login").onclick = () => {
    const user = document.querySelector("#username").value;
    const password = document.querySelector("#password").value;
    if (user && password) location.href = "/chat";
  };
}, 800);
</script>
</body>
"""

SSO_LOGIN_HTML = """<!doctype html>
<button>Continue with Keycloak</button>
<script>
document.querySelector("button").onclick = () => { location.href = "/chat"; };
</script>
"""


@pytest.fixture
def serve_routes() -> Iterator[Callable[[dict[str, str]], str]]:
    servers: list[ThreadingHTTPServer] = []

    def _start(routes: dict[str, str]) -> str:
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format: str, *args: object) -> None:
                del format, args

            def do_GET(self) -> None:
                body = routes.get(self.path)
                if body is None:
                    self.send_error(404)
                    return
                data = body.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        servers.append(server)
        host, port = server.server_address
        return f"http://{host}:{port}"

    yield _start
    for server in servers:
        server.shutdown()


def test_login_keycloak_fills_delayed_keycloak_form(
    page: Page, serve_routes: Callable[[dict[str, str]], str]
) -> None:
    origin = serve_routes(
        {
            "/login": LOGIN_HTML,
            "/auth": DELAYED_AUTH_HTML,
            "/chat": CHAT_HTML,
        }
    )
    login_keycloak(page, origin, "dev", "dev")
    expect(page.locator("#chat-input")).to_be_visible()


def test_login_keycloak_skips_form_when_chat_already_visible(
    page: Page, serve_routes: Callable[[dict[str, str]], str]
) -> None:
    origin = serve_routes({"/login": SSO_LOGIN_HTML, "/chat": CHAT_HTML})
    login_keycloak(page, origin, "dev", "dev")
    expect(page.locator("#chat-input")).to_be_visible()
