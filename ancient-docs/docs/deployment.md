# SHAKODS Deployment Guide

## Local development

### Prerequisites

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) (recommended) or pip
- Docker (for Postgres + PostGIS)

### 1. Clone and install

```bash
cd shakods
uv sync
# or: pip install -e .
```

### 2. Start Postgres (Docker)

Postgres is mapped to **host port 5434** to avoid conflict with a local PostgreSQL on 5432.

```bash
cd infrastructure/local
docker compose up -d postgres
```

Connection URL: `postgresql+asyncpg://shakods:shakods@127.0.0.1:5434/shakods`

### 3. Run migrations

From the `shakods` project root:

```bash
uv run alembic -c infrastructure/local/alembic.ini upgrade head
# or: uv run python -m shakods.scripts.alembic_runner upgrade
```

If you have `DATABASE_URL` or another URL pointing at port 5432, the Alembic env will rewrite localhost:5432 to 5434 so migrations hit the Docker Postgres.

### 4. Start the API

```bash
uv run uvicorn shakods.api.server:app --reload --host 0.0.0.0 --port 8000
```

See [database.md](database.md) for more on Postgres, URLs, and migrations.

---

## AWS deployment

### Prerequisites

- AWS CLI configured (profile/credentials)
- jq (for deploy script)
- Bash

### Architecture

- **CloudFormation stacks**: `shakods-{env}-base`, `-db`, `-lambda`, `-api`
- **Step Functions**: REACT orchestrator state machine (optional)
- **Lambda**: API handler (API Gateway), message handler (SQS/webhook)

### Deploy steps

From the `shakods` project root:

```bash
cd infrastructure/aws/scripts
./deploy.sh staging us-east-1
```

This will:

1. Build Lambda layers (optional no-op)
2. Deploy **base** (Step Functions role, etc.)
3. Deploy **database** (DynamoDB state and sessions tables)
4. Deploy **Lambda** (api-handler, message-handler) and update code from `deploy_lambda.sh`
5. Deploy **API Gateway** (REST API → Lambda)
6. Create or update **Step Functions** state machine

### Deploy Lambda code only

After changing application or handler code:

```bash
./deploy_lambda.sh staging us-east-1
```

This builds a zip from the `shakods` package and dependencies, then updates the Lambda function code and handler.

### Configuration

- **JWT**: Set `JWT_SECRET` (and optionally `JWT_EXPIRE_MINUTES`) in the Lambda environment (e.g. via CloudFormation or console). Prefer AWS Secrets Manager and reference in the template.
- **Step Functions**: Set `STEP_FUNCTIONS_ORCHESTRATOR_ARN` and optionally `ORCHESTRATOR_LAMBDA_ARN` on the API Lambda so `/orchestrate` can start the state machine.
- **DynamoDB**: Table names are `shakods-{env}-state` and `shakods-{env}-sessions`; the Lambda execution role is scoped to `shakods-{env}-*` tables.

### Outputs

After deploy:

- **API endpoint**: From stack `shakods-{env}-api`, output `ApiEndpoint`
- **State machine ARN**: `arn:aws:states:{region}:{account}:stateMachine:shakods-{env}-orchestrator`

### Teardown

```bash
./teardown.sh staging us-east-1
```

Deletes the CloudFormation stacks and the Step Functions state machine in reverse order.

---

## Remote receiver (Raspberry Pi)

See `remote_receiver/README.md` and `remote_receiver/scripts/deploy_receiver.sh` for deploying the receiver service to a Pi (SDR, signal processing, HQ upload).
