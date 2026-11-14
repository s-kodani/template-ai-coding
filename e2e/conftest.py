"""Real Open WebUI / Keycloak browser fixtures; run explicitly with pytest e2e/."""
from __future__ import annotations

import os
import re
import shutil
import time
import urllib.request
from collections.abc import Callable
from pathlib import Path

import pytest
from playwright.sync_api import Error, Locator, Page, expect
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BASE_URL = "http://localhost:8080"
CHAT_TIMEOUT_MS = 120_000
_TRANSIENT_GOTO = (
    "ERR_SOCKET_NOT_CONNECTED", "ERR_CONNECTION_REFUSED", "ERR_CONNECTION_RESET",
    "ERR_CONNECTION_CLOSED", "ERR_EMPTY_RESPONSE", "ERR_ABORTED",
)


def _load_repo_env() -> None:
    path = REPO_ROOT / ".env"
    if path.is_file():
        for raw in path.read_text().splitlines():
            if raw.strip() and not raw.lstrip().startswith("#") and "=" in raw:
                key, _, value = raw.partition("=")
                os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


_load_repo_env()


def wait_for_http(url: str, *, timeout_s: float = 60, sleep: Callable = time.sleep) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=3):
                return
        except OSError:
            sleep(.25)
    raise RuntimeError(f"Timed out waiting for HTTP {url}")


def goto_webui(page: Page, url: str, *, timeout_s: float = 30) -> None:
    deadline = time.monotonic() + timeout_s
    while True:
        try:
            page.goto(url, wait_until="domcontentloaded")
            return
        except Error as exc:
            if time.monotonic() >= deadline or not any(code in str(exc) for code in _TRANSIENT_GOTO):
                raise
            time.sleep(.25)


def login_keycloak(page: Page, webui_url: str, username: str, password: str) -> None:
    goto_webui(page, f"{webui_url}/auth")
    chat = page.locator("#chat-input")
    provider = page.get_by_role("button", name=re.compile("Keycloak", re.IGNORECASE)).or_(
        page.get_by_role("link", name=re.compile("Keycloak", re.IGNORECASE))
    )
    welcome = page.get_by_role("button", name=re.compile(r"^(Get started|はじめる|始める)$", re.IGNORECASE))
    expect(welcome.or_(provider).or_(chat)).to_be_visible(timeout=30_000)
    if welcome.is_visible():
        welcome.click()
    expect(provider.or_(chat)).to_be_visible(timeout=30_000)
    if chat.is_visible():
        return
    provider.click()
    username_field = page.locator("#username")
    expect(username_field.or_(chat)).to_be_visible(timeout=30_000)
    if username_field.is_visible():
        username_field.fill(username)
        page.locator("#password").fill(password)
        page.locator("#kc-login").click()
    expect(chat).to_be_visible(timeout=60_000)
    changelog = page.get_by_role("dialog", name=re.compile("新機能|What.s New", re.IGNORECASE))
    try:
        changelog.wait_for(state="visible", timeout=1500)
    except PlaywrightTimeoutError:
        pass
    else:
        changelog.get_by_role("button", name=re.compile(r"^(Close|閉じる)$")).click()
        expect(changelog).not_to_be_visible()


def auth_headers(page: Page) -> dict[str, str]:
    token = page.evaluate('() => localStorage.getItem("token")')
    assert token, "Authenticated Open WebUI session required"
    return {"Authorization": f"Bearer {token}"}


def tools_catalog(page: Page, webui_url: str) -> list[dict]:
    response = page.request.get(f"{webui_url}/api/v1/tools/", headers=auth_headers(page))
    assert response.ok, "Cannot read the authenticated tool catalog"
    return response.json()


def send_chat(page: Page, prompt: str, *, timeout_ms: int = CHAT_TIMEOUT_MS) -> Locator:
    expect(page.get_by_role("button", name=re.compile(r"^(Select a model|モデルを選択)\s*$"))).not_to_be_visible(timeout=10_000)
    replies = page.locator(".chat-assistant")
    before = replies.count()
    page.locator("#chat-input").fill(prompt)
    update_notice = page.locator(".absolute.bottom-8.right-8.z-50").filter(
        has=page.locator('a[href="https://github.com/open-webui/open-webui/releases"]')
    )
    if update_notice.is_visible():
        update_notice.get_by_role("button", name=re.compile(r"^(Close|閉じる)$")).click()
    page.locator("#send-message-button").click()
    expect(replies).to_have_count(before + 1, timeout=timeout_ms)
    reply = replies.last
    expect(reply.locator("#response-content-container")).to_contain_text(re.compile(r"\S"), timeout=timeout_ms)
    expect(page.get_by_role("button", name=re.compile(r"^(Stop|停止)$"))).not_to_be_visible(timeout=timeout_ms)
    return reply


def reply_contains_any(reply: Locator, *needles: str) -> bool:
    return any(value in reply.inner_text() for value in needles)


def reply_contains_seed_knowledge(reply: Locator) -> bool:
    return reply_contains_any(reply, "FastMCP", "pgvector", "Open WebUI", "Langfuse")


def reply_contains_url(reply: Locator) -> bool:
    return bool(re.search(r"https?://", reply.inner_text()))


def logout_webui(page: Page, webui_url: str) -> None:
    response = page.request.post(f"{webui_url}/api/v1/auths/signout", headers=auth_headers(page))
    assert response.ok, "Open WebUI signout failed"
    page.evaluate('() => localStorage.removeItem("token")')
    page.context.clear_cookies()
    goto_webui(page, f"{webui_url}/auth")


def pytest_configure(config: pytest.Config) -> None:
    if not getattr(config.option, "base_url", None):
        config.option.base_url = os.environ.get("E2E_BASE_URL") or DEFAULT_BASE_URL


@pytest.fixture(scope="session")
def webui_url() -> str:
    url = (os.environ.get("E2E_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
    wait_for_http(f"{url}/ready")
    return url


@pytest.fixture(scope="session")
def browser_type_launch_args(browser_type_launch_args: dict) -> dict:
    args = dict(browser_type_launch_args)
    args["args"] = [*args.get("args", []), "--no-sandbox", "--disable-dev-shm-usage"]
    channel = os.environ.get("E2E_BROWSER_CHANNEL")
    if channel is None and (shutil.which("google-chrome") or Path("/Applications/Google Chrome.app").exists()):
        channel = "chrome"
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
    value = os.environ.get("OPENAI_API_KEY", "")
    if not value:
        pytest.skip("OPENAI_API_KEY is not configured")
    return value


@pytest.fixture(scope="session")
def brave_search_api_key() -> str:
    value = os.environ.get("BRAVE_SEARCH_API_KEY", "")
    if not value:
        pytest.skip("BRAVE_SEARCH_API_KEY is not configured")
    return value


@pytest.fixture(scope="session")
def require_empty_brave_search_api_key() -> None:
    if os.environ.get("BRAVE_SEARCH_API_KEY"):
        pytest.skip("Requires empty BRAVE_SEARCH_API_KEY")


@pytest.fixture
def logged_in_dev(page: Page, webui_url: str, e2e_username: str, e2e_password: str) -> Page:
    login_keycloak(page, webui_url, e2e_username, e2e_password)
    return page


@pytest.fixture
def logged_in_dev2(page: Page, webui_url: str, e2e_dev2_username: str, e2e_dev2_password: str) -> Page:
    login_keycloak(page, webui_url, e2e_dev2_username, e2e_dev2_password)
    return page
