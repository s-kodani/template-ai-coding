from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAKEFILE = (ROOT / "infra" / "Makefile").read_text(encoding="utf-8")
COMPOSE = (ROOT / "infra" / "langflow" / "compose.yml").read_text(encoding="utf-8")
INIT_SQL = (ROOT / "infra" / "langflow" / "init.sql").read_text(encoding="utf-8")


def test_default_up_excludes_langflow() -> None:
    assert "up: langfuse-up app-up" in MAKEFILE
    assert "down: app-down langfuse-down" in MAKEFILE
    assert "langflow-up:" in MAKEFILE
    assert "langflow-down:" in MAKEFILE


def test_langflow_compose_is_isolated_from_app_postgres() -> None:
    assert "\n  langflow:\n" in COMPOSE
    assert "\n  langflow-postgres:\n" in COMPOSE
    assert "langflowai/langflow:1.11.4" in COMPOSE
    assert "7860:7860" in COMPOSE
    assert "OPENAI_API_KEY" in COMPOSE
    assert "external:" not in COMPOSE
    assert "LANGFLOW_DATABASE_URL: postgresql://" in COMPOSE
    assert "@langflow-postgres:5432/" in COMPOSE
    assert "CREATE DATABASE langflow_vectors" in INIT_SQL
    assert "CREATE EXTENSION IF NOT EXISTS vector" in INIT_SQL
