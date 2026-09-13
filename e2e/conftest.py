"""Playwright e2e fixtures. Collected only when pytest is pointed at e2e/."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest
from playwright.sync_api import Page

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BASE_URL = "http://localhost:8080"


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


def pytest_configure(config: pytest.Config) -> None:
    current = getattr(config.option, "base_url", None)
    if not current:
        config.option.base_url = os.environ.get("E2E_BASE_URL") or DEFAULT_BASE_URL


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
def openai_api_key() -> str:
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        pytest.skip("OPENAI_API_KEY is not set")
    return key


@pytest.fixture
def page(page: Page) -> Page:
    page.set_default_timeout(60_000)
    page.set_default_navigation_timeout(60_000)
    return page
