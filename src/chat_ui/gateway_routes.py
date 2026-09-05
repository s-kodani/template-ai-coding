from __future__ import annotations

from typing import Annotated, Any

from chainlit.auth import get_current_user
from chainlit.user import PersistedUser, User
from fastapi import Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from chat_ui.gateway_session import apply_ui_gateway_toggle

CurrentUser = Annotated[User | PersistedUser | None, Depends(get_current_user)]


class GatewayMCPToggleRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    sessionId: str
    name: str


def register_gateway_mcp_routes(
    app: Any,
    *,
    name_to_id: dict[str, str],
) -> None:
    from chainlit.context import init_ws_context
    from chainlit.session import WebsocketSession
    from chainlit.user_session import user_sessions

    def _session_store(session: Any) -> dict[str, Any]:
        return user_sessions.setdefault(session.id, {})

    def _authorize(session: Any, current_user: User | PersistedUser | None) -> None:
        if current_user and (
            not session.user or session.user.identifier != current_user.identifier
        ):
            raise HTTPException(status_code=401)

    @app.post("/gateway-mcp")
    async def connect_gateway_mcp(
        payload: GatewayMCPToggleRequest,
        current_user: CurrentUser,
    ) -> JSONResponse:
        session = WebsocketSession.get_by_id(payload.sessionId)
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found")
        _authorize(session, current_user)
        init_ws_context(session)
        result = apply_ui_gateway_toggle(
            _session_store(session),
            ui_name=payload.name,
            enable=True,
            name_to_id=name_to_id,
        )
        if not result.get("success"):
            raise HTTPException(status_code=404, detail=result.get("error"))
        return JSONResponse(content=result)

    @app.delete("/gateway-mcp")
    async def disconnect_gateway_mcp(
        payload: GatewayMCPToggleRequest,
        current_user: CurrentUser,
    ) -> JSONResponse:
        session = WebsocketSession.get_by_id(payload.sessionId)
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found")
        _authorize(session, current_user)
        init_ws_context(session)
        result = apply_ui_gateway_toggle(
            _session_store(session),
            ui_name=payload.name,
            enable=False,
            name_to_id=name_to_id,
        )
        if not result.get("success"):
            raise HTTPException(status_code=404, detail=result.get("error"))
        return JSONResponse(content=result)
