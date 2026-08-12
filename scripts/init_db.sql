-- Postgres initialization script
-- Runs once when the container first starts (docker-entrypoint-initdb.d/)
-- Enables the pgvector extension — required for clause embedding storage.

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS vector;
