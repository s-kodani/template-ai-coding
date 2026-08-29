from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Principal:
    subject: str
    issuer: str
    authorized_party: str
    roles: frozenset[str]
    scopes: frozenset[str]
    token: str
