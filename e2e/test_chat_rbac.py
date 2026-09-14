"""RBAC e2e: role-restricted users must not retrieve seeded knowledge."""

from __future__ import annotations

from conftest import login_keycloak, reply_contains_seed_knowledge, send_chat
from playwright.sync_api import Page

KNOWLEDGE_PROMPT = (
    "search_knowledge ツールで「Architecture Overview」を検索し、"
    "見つかった内容を1文で要約してください。"
)


def test_dev2_cannot_retrieve_seeded_knowledge(
    page: Page,
    chainlit_url: str,
    e2e_dev2_username: str,
    e2e_dev2_password: str,
    openai_api_key: str,
) -> None:
    del openai_api_key

    login_keycloak(page, chainlit_url, e2e_dev2_username, e2e_dev2_password)
    reply = send_chat(page, KNOWLEDGE_PROMPT)
    assert not reply_contains_seed_knowledge(reply)


def test_readerless_cannot_retrieve_seeded_knowledge(
    page: Page,
    chainlit_url: str,
    e2e_readerless_username: str,
    e2e_readerless_password: str,
    openai_api_key: str,
) -> None:
    del openai_api_key

    login_keycloak(
        page,
        chainlit_url,
        e2e_readerless_username,
        e2e_readerless_password,
    )
    reply = send_chat(page, KNOWLEDGE_PROMPT)
    assert not reply_contains_seed_knowledge(reply)
