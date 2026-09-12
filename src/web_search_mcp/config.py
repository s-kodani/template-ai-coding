from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    brave_search_api_key: str = ""
    brave_search_base_url: str = "https://api.search.brave.com/res/v1/web/search"
    search_timeout: float = 15.0

    mcp_host: str = "127.0.0.1"
    mcp_port: int = 8001
    mcp_path: str = "/mcp"
    mcp_jwks_uri: str = ""
    mcp_issuer: str = "http://localhost:8081/realms/knowledge"
    mcp_audience: str = "http://localhost:8001/mcp"
    mcp_authorization_server: str = "http://localhost:8081/realms/knowledge"
    mcp_resource_base_url: str = "http://localhost:8001"

    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "http://localhost:3000"
    langfuse_tracing_enabled: bool = True
    langfuse_tracing_environment: str = ""
    langfuse_release: str = ""

    @property
    def langfuse_configured(self) -> bool:
        return bool(self.langfuse_public_key and self.langfuse_secret_key)


def get_settings() -> Settings:
    return Settings()
