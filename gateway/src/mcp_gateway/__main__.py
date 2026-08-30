from mcp_gateway.config import Settings


def main() -> None:
    import uvicorn

    settings = Settings()
    uvicorn.run("mcp_gateway.app:create_app", factory=True, host=settings.host, port=settings.port)


if __name__ == "__main__":
    main()
