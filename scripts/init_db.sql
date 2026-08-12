-- Postgres initialization script
-- Runs once when the container first starts (docker-entrypoint-initdb.d/)
-- Enables the pgvector extension — required for clause embedding storage.

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS vector;

-- ---------------------------------------------------------------------------
-- Runtime application role (M1)
--
-- The FastAPI application connects as app_user, which is NOT a superuser
-- and does NOT have BYPASSRLS.  This guarantees that Row-Level Security
-- policies are enforced at the database layer.
--
-- The migration / admin role (contract_user) retains full privileges and
-- is used only by Alembic and ad-hoc admin scripts.
-- ---------------------------------------------------------------------------

DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'app_user') THEN
        CREATE ROLE app_user WITH LOGIN PASSWORD 'app_pass' NOSUPERUSER NOBYPASSRLS;
    END IF;
END
$$;

GRANT CONNECT ON DATABASE contract_risk_db TO app_user;
GRANT USAGE ON SCHEMA public TO app_user;

-- Auto-grant on objects created by the migration role (contract_user)
ALTER DEFAULT PRIVILEGES FOR ROLE contract_user IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO app_user;
ALTER DEFAULT PRIVILEGES FOR ROLE contract_user IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO app_user;
ALTER DEFAULT PRIVILEGES FOR ROLE contract_user IN SCHEMA public
    GRANT EXECUTE ON FUNCTIONS TO app_user;
