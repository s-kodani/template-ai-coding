from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    keycloak_issuer: str = "http://localhost:8081/realms/knowledge"
    keycloak_jwks_uri: str = (
        "http://keycloak:8080/realms/knowledge/protocol/openid-connect/certs"
    )
    keycloak_token_url: str = (
        "http://keycloak:8080/realms/knowledge/protocol/openid-connect/token"
    )
    gateway_audience: str = "mcp-gateway"
    gateway_azp: str = "chainlit"
    gateway_client_id: str = "mcp-gateway"
    gateway_client_secret: str = "mcp-gateway-local-secret"
    registry_path: str = "infra/app/gateway-registry.yml"
    host: str = "127.0.0.1"
    port: int = 8082
    token_cache_ttl_seconds: int = 300
    mcp_call_timeout_seconds: float = 30.0
    token_exchange_timeout_seconds: float = 5.0
