from __future__ import annotations

import base64
import json

from chat_ui.jwt_util import jwt_claims


def _unsigned(payload: dict) -> str:
    body = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()
    return f"h.{body}.s"


def test_jwt_claims_reads_payload() -> None:
    claims = jwt_claims(_unsigned({"sub": "u1", "exp": 1_900_000_000}))
    assert claims["sub"] == "u1"
    assert claims["exp"] == 1_900_000_000


def test_jwt_claims_returns_empty_for_malformed_token() -> None:
    assert jwt_claims("not-a-jwt") == {}
