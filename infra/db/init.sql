-- Enable the pgvector extension on first DB init.
-- Mounted into /docker-entrypoint-initdb.d/ by docker-compose so the extension
-- exists independently of the application migrations (#3).
CREATE EXTENSION IF NOT EXISTS vector;
