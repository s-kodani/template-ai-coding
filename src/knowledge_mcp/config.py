from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://knowledge:knowledge@localhost:5433/knowledge"
    postgres_user: str = "knowledge"
    postgres_password: str = "change-me"
    postgres_db: str = "knowledge"
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536
    chat_model: str = "gpt-4o-mini"

    mcp_host: str = "127.0.0.1"
    mcp_port: int = 8000
    mcp_path: str = "/mcp"
    mcp_server_url: str = "http://localhost:8000/mcp"
    mcp_bearer_token: str = ""

    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "http://localhost:3000"
    langfuse_tracing_enabled: bool = True

    embedding_timeout: float = 30.0
    db_timeout: float = 10.0
    langflow_vectors_url: str = "postgresql://langflow:langflow@localhost:5434/langflow_vectors"
    langflow_collection_name: str = "knowledge_documents_v1"

    @property
    def langfuse_configured(self) -> bool:
        return bool(self.langfuse_public_key and self.langfuse_secret_key)

    @property
    def host_database_url(self) -> str:
        """ホストマシンから Postgres に接続する URL（compose の 5433 公開ポート）。"""
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@localhost:5433/{self.postgres_db}"
        )


def get_settings() -> Settings:
    return Settings()
