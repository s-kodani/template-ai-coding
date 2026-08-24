-- Langflow メタデータ DB（POSTGRES_DB=langflow）とは別に、
-- PoC 用 PGVector を置く。同一インスタンス・別データベース。
CREATE DATABASE langflow_vectors;

\connect langflow_vectors
CREATE EXTENSION IF NOT EXISTS vector;
