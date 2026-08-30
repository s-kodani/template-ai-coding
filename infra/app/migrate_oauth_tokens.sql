CREATE TABLE IF NOT EXISTS chainlit_oauth_tokens (
    subject TEXT PRIMARY KEY,
    session_id TEXT UNIQUE,
    access_token_enc BYTEA NOT NULL,
    refresh_token_enc BYTEA,
    expires_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
