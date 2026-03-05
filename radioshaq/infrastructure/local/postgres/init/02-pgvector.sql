-- Optional: required only when Hindsight uses the same PostgreSQL instance.
-- If the image does not include pgvector, use an image that does (e.g. ankane/pgvector)
-- or install pgvector in a custom Dockerfile.
CREATE EXTENSION IF NOT EXISTS vector;
