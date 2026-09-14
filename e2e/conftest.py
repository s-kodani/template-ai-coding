"""Playwright e2e fixtures. Collected only when pytest is pointed at e2e/."""

from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import asyncpg
import pytest
from playwright.sync_api import APIResponse, Locator, Page, Response, expect

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BASE_URL = "http://localhost:8080"
CHAT_TIMEOUT_MS = 120_000
MCP_STORAGE_KEY = "mcp_storage_key"
REAUTH_REQUIRED_DETAIL = "Keycloak セッションが無効です。再ログインしてください"
_KEYCLOAK_PROVIDER = re.compile(r"keycloak", re.IGNORECASE)


def _load_repo_env() -> None:
    path = REPO_ROOT / ".env"
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        os.environ.setdefault(key, value)


_load_repo_env()


def _browser_channel() -> str | None:
    override = os.environ.get("E2E_BROWSER_CHANNEL")
    if override is not None:
        return override or None
    if shutil.which("google-chrome") or shutil.which("google-chrome-stable"):
        return "chrome"
    return None


def login_keycloak(page: Page, chainlit_url: str, username: str, password: str) -> None:
    page.goto(f"{chainlit_url}/login", wait_until="domcontentloaded")
    page.get_by_role("button", name=_KEYCLOAK_PROVIDER).click()
    username_field = page.locator("#username")
    if username_field.is_visible(timeout=5_000):
        username_field.fill(username)
        page.locator("#password").fill(password)
        page.locator("#kc-login").click()
    expect(page.locator("#chat-input")).to_be_visible(timeout=60_000)


def send_chat(page: Page, prompt: str, *, timeout_ms: int = CHAT_TIMEOUT_MS) -> Locator:
    chat_input = page.locator("#chat-input")
    chat_input.fill(prompt)
    page.locator("#chat-submit").click()
    reply = page.locator('[data-step-type="assistant_message"]').last
    expect(reply).to_be_visible(timeout=timeout_ms)
    return reply


def expect_mcp_post(
    page: Page,
    *,
    server_name: str | None = None,
    timeout_ms: int = 60_000,
):
    def _matches(response: Response) -> bool:
        if "/mcp" not in response.url or response.request.method != "POST":
            return False
        return not server_name or server_name in (response.request.post_data or "")

    return page.expect_response(_matches, timeout=timeout_ms)


def reply_contains_any(reply: Locator, *needles: str) -> bool:
    text = reply.inner_text()
    return any(needle in text for needle in needles)


def reply_contains_seed_knowledge(reply: Locator) -> bool:
    return reply_contains_any(reply, "FastMCP", "pgvector", "Chainlit", "Langfuse")


def reply_contains_url(reply: Locator) -> bool:
    text = reply.inner_text()
    return "http://" in text or "https://" in text


def parse_session_id(post_data: str | None) -> str:
    payload = json.loads(post_data or "{}")
    session_id = payload.get("sessionId")
    if not session_id:
        msg = "sessionId was not found in POST /mcp body"
        raise AssertionError(msg)
    return str(session_id)


def capture_session_id_from_response(response: Response) -> str:
    return parse_session_id(response.request.post_data)


def mcp_api_request(
    page: Page,
    chainlit_url: str,
    method: str,
    session_id: str,
    server_name: str,
) -> APIResponse:
    url = f"{chainlit_url.rstrip('/')}/mcp"
    body = json.dumps({"sessionId": session_id, "name": server_name})
    headers = {"Content-Type": "application/json"}
    if method == "POST":
        return page.request.post(url, data=body, headers=headers)
    return page.request.delete(url, data=body, headers=headers)


def mcp_connect(
    page: Page,
    chainlit_url: str,
    session_id: str,
    server_name: str,
) -> APIResponse:
    response = mcp_api_request(page, chainlit_url, "POST", session_id, server_name)
    assert response.ok, response.text()
    return response


def mcp_disconnect(
    page: Page,
    chainlit_url: str,
    session_id: str,
    server_name: str,
) -> APIResponse:
    response = mcp_api_request(page, chainlit_url, "DELETE", session_id, server_name)
    assert response.ok, response.text()
    return response


def logout_chainlit(page: Page, chainlit_url: str) -> None:
    response = page.request.post(f"{chainlit_url.rstrip('/')}/logout")
    assert response.ok, response.text()


def read_mcp_storage_names(page: Page) -> list[str]:
    raw = page.evaluate(
        f"() => localStorage.getItem({json.dumps(MCP_STORAGE_KEY)}) || '[]'"
    )
    entries = json.loads(raw)
    return [str(item.get("name")) for item in entries if item.get("name")]


async def _clear_oauth_tokens_async(session_id: str) -> None:
    url = os.environ.get(
        "TOKEN_STORE_DATABASE_URL",
        "postgresql://knowledge:change-me@localhost:5433/knowledge",
    )
    conn = await asyncpg.connect(url)
    try:
        await conn.execute(
            "DELETE FROM chainlit_oauth_tokens WHERE session_id = $1",
            session_id,
        )
    finally:
        await conn.close()


def clear_oauth_tokens(session_id: str) -> None:
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(asyncio.run, _clear_oauth_tokens_async(session_id))
        future.result()


def pytest_configure(config: pytest.Config) -> None:
    current = getattr(config.option, "base_url", None)
    if not current:
        config.option.base_url = os.environ.get("E2E_BASE_URL") or DEFAULT_BASE_URL
    config.addinivalue_line("markers", "e2e_smoke: minimal Playwright smoke subset")
    config.addinivalue_line("markers", "e2e_brave: requires or validates BRAVE_SEARCH_API_KEY")
    config.addinivalue_line("markers", "e2e_reauth: manipulates OAuth token store")


@pytest.fixture(scope="session")
def chainlit_url() -> str:
    return (os.environ.get("E2E_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")


@pytest.fixture(scope="session")
def browser_type_launch_args(browser_type_launch_args: dict) -> dict:
    args = dict(browser_type_launch_args)
    extra = list(args.get("args") or [])
    extra.extend(["--no-sandbox", "--disable-dev-shm-usage"])
    args["args"] = extra
    channel = _browser_channel()
    if channel:
        args["channel"] = channel
    return args


@pytest.fixture(scope="session")
def e2e_username() -> str:
    return os.environ.get("E2E_USERNAME", "dev")


@pytest.fixture(scope="session")
def e2e_password() -> str:
    return os.environ.get("E2E_PASSWORD", "dev")


@pytest.fixture(scope="session")
def e2e_dev2_username() -> str:
    return os.environ.get("E2E_DEV2_USERNAME", "dev2")


@pytest.fixture(scope="session")
def e2e_dev2_password() -> str:
    return os.environ.get("E2E_DEV2_PASSWORD", "dev2")


@pytest.fixture(scope="session")
def e2e_readerless_username() -> str:
    return os.environ.get("E2E_READERLESS_USERNAME", "readerless")


@pytest.fixture(scope="session")
def e2e_readerless_password() -> str:
    return os.environ.get("E2E_READERLESS_PASSWORD", "readerless")


@pytest.fixture(scope="session")
def openai_api_key() -> str:
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        pytest.skip("OPENAI_API_KEY is not set")
    return key


@pytest.fixture(scope="session")
def brave_search_api_key() -> str:
    key = os.environ.get("BRAVE_SEARCH_API_KEY", "").strip()
    if not key:
        pytest.skip("BRAVE_SEARCH_API_KEY is not set")
    return key


@pytest.fixture(scope="session")
def require_empty_brave_search_api_key() -> None:
    if os.environ.get("BRAVE_SEARCH_API_KEY", "").strip():
        pytest.skip("BRAVE_SEARCH_API_KEY is set; run without it to verify the error path")


@pytest.fixture
def page(page: Page) -> Page:
    page.set_default_timeout(60_000)
    page.set_default_navigation_timeout(60_000)
    return page


@pytest.fixture
def logged_in_dev(
    page: Page,
    chainlit_url: str,
    e2e_username: str,
    e2e_password: str,
) -> Page:
    with expect_mcp_post(page, server_name="knowledge-mcp") as response_info:
        login_keycloak(page, chainlit_url, e2e_username, e2e_password)
    assert response_info.value.status == 200
    return page


@pytest.fixture
def logged_in_dev2(
    page: Page,
    chainlit_url: str,
    e2e_dev2_username: str,
    e2e_dev2_password: str,
) -> Page:
    with expect_mcp_post(page, server_name="web-search-mcp") as response_info:
        login_keycloak(page, chainlit_url, e2e_dev2_username, e2e_dev2_password)
    assert response_info.value.status == 200
    return page


@pytest.fixture
def chainlit_session_id(
    page: Page,
    chainlit_url: str,
    e2e_username: str,
    e2e_password: str,
) -> str:
    with expect_mcp_post(page, server_name="knowledge-mcp") as response_info:
        login_keycloak(page, chainlit_url, e2e_username, e2e_password)
    assert response_info.value.status == 200
    return capture_session_id_from_response(response_info.value)


@pytest.fixture
def chainlit_session_id_dev2(
    page: Page,
    chainlit_url: str,
    e2e_dev2_username: str,
    e2e_dev2_password: str,
) -> str:
    with expect_mcp_post(page, server_name="web-search-mcp") as response_info:
        login_keycloak(page, chainlit_url, e2e_dev2_username, e2e_dev2_password)
    assert response_info.value.status == 200
    return capture_session_id_from_response(response_info.value)
