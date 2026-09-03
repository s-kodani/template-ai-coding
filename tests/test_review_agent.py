import re
from pathlib import Path

REVIEW_AGENT = Path(__file__).resolve().parents[1] / ".apm" / "agents" / "review.agent.md"


def test_review_agent_resolves_skill_from_apm_install_destination() -> None:
    text = REVIEW_AGENT.read_text(encoding="utf-8")

    assert "implementation-workflow" in text
    assert "review-and-compliance.md" in text
    assert "apm install" in text
    assert "レビュー用サブエージェント" in text
    assert re.search(r"[./]skills/", text) is None
