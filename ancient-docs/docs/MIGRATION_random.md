# Alembic migrations and database credentials

## Docker (Postgres in containers)

If Postgres runs via **Docker** (`infrastructure/local/docker-compose.yml`), it’s on **host port 5434** (not 5432). The image already creates user `radioshaq`, password `radioshaq`, and database `radioshaq`.

**1. Start Postgres (from repo root):**
```powershell
cd c:\Users\MeMyself\monorepo\radioshaq\infrastructure\local
docker compose up -d postgres
```

**2. Run migrations (from repo root; point at port 5434):**
```powershell
cd c:\Users\MeMyself\monorepo\radioshaq
$env:POSTGRES_PORT = "5434"
.\.venv\Scripts\python.exe -m alembic upgrade head
```

If you need to run SQL inside the container (e.g. create user/DB by hand):
```powershell
docker exec -it radioshaq-postgres psql -U radioshaq -d radioshaq -c "CREATE EXTENSION IF NOT EXISTS postgis;"
```
Or open an interactive psql session:
```powershell
docker exec -it radioshaq-postgres psql -U radioshaq -d radioshaq
```
Then type SQL (e.g. `CREATE EXTENSION IF NOT EXISTS postgis;`) and `\q` to exit.

---

## Quick fix: use your current Postgres user

If you get **"password authentication failed for user radioshaq"**, your Postgres is using different credentials. Run migrations with the user/password that work for you:

**PowerShell (one-off):**
```powershell
cd radioshaq
$env:POSTGRES_USER = "postgres"   # or your actual username
$env:POSTGRES_PASSWORD = "your_password"
.\.venv\Scripts\python.exe -m alembic upgrade head
```

**Or set a full URL:**
```powershell
$env:DATABASE_URL = "postgresql://postgres:your_password@localhost:5432/radioshaq"
.\.venv\Scripts\python.exe -m alembic upgrade head
```

Create the database if it doesn’t exist (in `psql` as superuser):
```sql
CREATE DATABASE radioshaq;
-- If you want the default app user for later:
CREATE USER radioshaq WITH PASSWORD 'radioshaq';
GRANT ALL PRIVILEGES ON DATABASE radioshaq TO radioshaq;
\c radioshaq
CREATE EXTENSION IF NOT EXISTS postgis;
```

Then run the migration command again.

---

## Running migrations

From the `radioshaq` directory with the venv activated:

```bash
# Check current revision
alembic current

# Apply all migrations (creates/updates tables)
alembic upgrade head

# Roll back one revision
alembic downgrade -1
```

## Database credentials

Alembic reads the database URL from the environment.

### Option 1: Old/default params (local testing)

To use the **default** local params (no `.env` or env vars):

- **User:** `radioshaq`
- **Password:** `radioshaq`
- **Host:** `localhost`
- **Port:** `5432`
- **Database:** `radioshaq`

Ensure Postgres has this user and database:

```bash
# In psql as superuser (e.g. postgres):
CREATE USER radioshaq WITH PASSWORD 'radioshaq';
CREATE DATABASE radioshaq OWNER radioshaq;
\c radioshaq
CREATE EXTENSION IF NOT EXISTS postgis;
```

Then run migrations (defaults will be used):

```bash
cd radioshaq
uv run python -m alembic upgrade head
```

### Option 2: Updated username/password

If you changed the Postgres user or password:

**A. Using a `.env` file (recommended)**

1. Copy the example: `cp .env.example .env`
2. Edit `.env` and set:
   - `POSTGRES_USER=` your postgres username  
   - `POSTGRES_PASSWORD=` your postgres password  
   - Optionally `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`
3. Load env and run (PowerShell):  
   `Get-Content .env | ForEach-Object { if ($_ -match '^([^#=]+)=(.*)$') { [Environment]::SetEnvironmentVariable($matches[1], $matches[2], 'Process') } }; uv run python -m alembic upgrade head`  
   Or (Bash): `set -a; source .env; set +a; alembic upgrade head`

**B. Using one-off env vars**

PowerShell:

```powershell
$env:POSTGRES_USER = "your_user"
$env:POSTGRES_PASSWORD = "your_password"
uv run python -m alembic upgrade head
```

Bash:

```bash
export POSTGRES_USER=your_user
export POSTGRES_PASSWORD=your_password
alembic upgrade head
```

**C. Using a full URL**

```powershell
$env:DATABASE_URL = "postgresql://your_user:your_password@localhost:5432/radioshaq"
uv run python -m alembic upgrade head
```

**Note:** If the app uses an async driver, use `postgresql+asyncpg://...` for the app; Alembic needs a sync URL (`postgresql://...`). The code strips `+asyncpg` when building the migration URL.
