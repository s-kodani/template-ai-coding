"""Create deterministic MCP connections and groups before starting Open WebUI."""

from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path
from typing import Any

GROUPS = ("knowledge-mcp-reader", "web-search-reader")


def configured_environment(environment: dict[str, str], registry: dict) -> dict[str, str]:
    env = dict(environment)
    model = env.get("CHAT_MODEL", "").strip()
    if not model:
        raise ValueError("CHAT_MODEL is required")
    connections = []
    for gateway in registry.get("gateways", []):
        base = gateway["url"].rstrip("/")
        for server_id, server in gateway.get("servers", {}).items():
            if not server.get("enabled", False):
                continue
            roles = server.get("authorization", {}).get("required_roles", [])
            if any(role not in GROUPS for role in roles):
                raise ValueError("MCP server requires a group that has not been provisioned")
            grants = [
                {"principal_type": "group", "principal_id": role, "permission": "read"}
                for role in roles
            ] or [{"principal_type": "user", "principal_id": "*", "permission": "read"}]
            connections.append(
                {
                    "url": f"{base}/mcp/{server_id}",
                    "path": "",
                    "type": "mcp",
                    "auth_type": "system_oauth",
                    "key": "",
                    "config": {"enable": True, "access_grants": grants},
                    "info": {"id": server_id, "name": server.get("ui", {}).get("name", server_id)},
                }
            )
    env.update(
        {
            "TOOL_SERVER_CONNECTIONS": json.dumps(connections),
            "DEFAULT_MODELS": model,
            "DEFAULT_MODEL_PARAMS": json.dumps({"function_calling": "native"}),
            "DEFAULT_MODEL_METADATA": json.dumps(
                {
                    "toolIds": [f"server:mcp:{item['info']['id']}" for item in connections],
                    "capabilities": {"builtin_tools": False, "usage": True},
                }
            ),
            "OPENAI_API_CONFIGS": json.dumps({"0": {"model_ids": [model]}}),
            "ENABLE_OTEL": "false",
            "ENABLE_TITLE_GENERATION": "false",
            "ENABLE_TAGS_GENERATION": "false",
            "ENABLE_FOLLOW_UP_GENERATION": "false",
        }
    )
    if env.get("OPENAI_BASE_URL"):
        env["OPENAI_API_BASE_URL"] = env["OPENAI_BASE_URL"]
    return env


async def ensure_groups(find: Any, insert: Any) -> None:
    for name in GROUPS:
        existing = await find(name)
        if existing is None:
            await insert(name, name)
        elif (existing.get("name") if isinstance(existing, dict) else existing.name) != name:
            raise RuntimeError("Provisioned MCP group has an unexpected name")


async def seed_groups() -> None:
    # Config import runs the upstream migrations before group tables are accessed.
    import open_webui.config  # noqa: F401
    from open_webui.internal.db import get_async_db_context
    from open_webui.models.groups import Group

    async with get_async_db_context() as db:

        async def find(group_id):
            return await db.get(Group, group_id)

        async def insert(group_id, name):
            now = int(time.time())
            db.add(
                Group(
                    id=group_id,
                    name=name,
                    user_id="system",
                    description="Keycloak MCP role",
                    data={},
                    meta={},
                    permissions={},
                    created_at=now,
                    updated_at=now,
                )
            )

        await ensure_groups(find, insert)
        await db.commit()


async def ensure_default_model(
    model: str, metadata: dict, params: dict, find, insert, grant_read
) -> None:
    existing = await find(model)
    if existing is None:
        await insert(
            {
                "id": model,
                "name": model,
                "base_model_id": None,
                "params": params,
                "meta": metadata,
                "access_grants": [
                    {"principal_type": "user", "principal_id": "*", "permission": "read"}
                ],
            }
        )
    elif (existing.get("user_id") if isinstance(existing, dict) else existing.user_id) == "system":
        # Keep administrator edits to the managed model's metadata and parameters.
        await grant_read(model)


async def seed_default_model() -> None:
    import open_webui.config  # noqa: F401
    from open_webui.models.access_grants import AccessGrants
    from open_webui.models.models import ModelForm, Models

    async def insert(payload):
        await Models.insert_new_model(ModelForm.model_validate(payload), user_id="system")

    async def grant_read(model):
        await AccessGrants.grant_access("model", model, "user", "*", "read")

    await ensure_default_model(
        os.environ["CHAT_MODEL"],
        json.loads(os.environ["DEFAULT_MODEL_METADATA"]),
        json.loads(os.environ["DEFAULT_MODEL_PARAMS"]),
        Models.get_model_by_id,
        insert,
        grant_read,
    )


def main() -> None:
    import yaml

    path = Path(os.getenv("MCP_GATEWAY_REGISTRY_PATH", "/app/infra/app/gateway-registry.yml"))
    with path.open() as source:
        registry = yaml.safe_load(source)
    os.environ.update(configured_environment(dict(os.environ), registry))
    if not os.environ.get("WEBUI_SECRET_KEY"):
        raise RuntimeError("WEBUI_SECRET_KEY is required for persistent OAuth and MCP Apps")
    asyncio.run(seed_groups())
    asyncio.run(seed_default_model())
    # Fixed entrypoint shipped by the pinned upstream image; no user arguments.
    os.execv("/bin/bash", ["bash", "/app/backend/start.sh"])  # nosec B606


if __name__ == "__main__":
    main()
