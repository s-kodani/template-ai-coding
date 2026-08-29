#!/usr/bin/env python3
"""Issue a knowledge-mcp Bearer token for MCP Inspector (local password grant + token exchange)."""

from __future__ import annotations

import argparse
import os
import sys

import httpx

EXCHANGE_GRANT = "urn:ietf:params:oauth:grant-type:token-exchange"
ACCESS_TYPE = "urn:ietf:params:oauth:token-type:access_token"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--token-url",
        default=os.environ.get(
            "OAUTH_GENERIC_TOKEN_URL",
            "http://localhost:8081/realms/knowledge/protocol/openid-connect/token",
        ),
    )
    parser.add_argument("--username", default="dev")
    parser.add_argument("--password", default="dev")
    parser.add_argument("--chainlit-client-id", default="chainlit")
    parser.add_argument(
        "--chainlit-client-secret",
        default=os.environ.get("OAUTH_GENERIC_CLIENT_SECRET", "chainlit-local-secret"),
    )
    parser.add_argument("--gateway-client-id", default="mcp-gateway")
    parser.add_argument(
        "--gateway-client-secret",
        default=os.environ.get("GATEWAY_CLIENT_SECRET", "mcp-gateway-local-secret"),
    )
    args = parser.parse_args()

    with httpx.Client(timeout=10.0) as client:
        password_grant = client.post(
            args.token_url,
            data={
                "grant_type": "password",
                "client_id": args.chainlit_client_id,
                "client_secret": args.chainlit_client_secret,
                "username": args.username,
                "password": args.password,
                "scope": "openid",
            },
        )
        if password_grant.status_code >= 400:
            print(password_grant.text, file=sys.stderr)
            return 1
        subject_token = password_grant.json().get("access_token")
        if not subject_token:
            print("password grant did not return access_token", file=sys.stderr)
            return 1
        exchanged = client.post(
            args.token_url,
            data={
                "grant_type": EXCHANGE_GRANT,
                "client_id": args.gateway_client_id,
                "client_secret": args.gateway_client_secret,
                "subject_token": subject_token,
                "subject_token_type": ACCESS_TYPE,
                "audience": "knowledge-mcp",
                "scope": "mcp-tools",
            },
        )
        if exchanged.status_code >= 400:
            print(exchanged.text, file=sys.stderr)
            return 1
        mcp_token = exchanged.json().get("access_token")
        if not mcp_token:
            print("token exchange did not return access_token", file=sys.stderr)
            return 1
    print(mcp_token)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
