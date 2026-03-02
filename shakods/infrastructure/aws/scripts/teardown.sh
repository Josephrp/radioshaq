#!/bin/bash
# Teardown SHAKODS AWS resources
# Usage: ./teardown.sh [environment] [region]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENVIRONMENT="${1:-staging}"
REGION="${2:-us-east-1}"
STACK_NAME="shakods-${ENVIRONMENT}"

echo "Tearing down SHAKODS stacks in ${REGION} (environment: ${ENVIRONMENT})"

# Delete in reverse dependency order
for STACK in "${STACK_NAME}-api" "${STACK_NAME}-lambda" "${STACK_NAME}-orchestrator" "${STACK_NAME}-db" "${STACK_NAME}-base"; do
  if aws cloudformation describe-stacks --stack-name "${STACK}" --region "${REGION}" 2>/dev/null; then
    echo "Deleting stack: ${STACK}"
    aws cloudformation delete-stack --stack-name "${STACK}" --region "${REGION}"
    aws cloudformation wait stack-delete-complete --stack-name "${STACK}" --region "${REGION}" || true
  fi
done

# Step Functions state machine (often created outside CF)
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
STATE_MACHINE_ARN="arn:aws:states:${REGION}:${ACCOUNT_ID}:stateMachine:${STACK_NAME}-orchestrator"
if aws stepfunctions describe-state-machine --state-machine-arn "${STATE_MACHINE_ARN}" --region "${REGION}" 2>/dev/null; then
  echo "Deleting state machine: ${STACK_NAME}-orchestrator"
  aws stepfunctions delete-state-machine --state-machine-arn "${STATE_MACHINE_ARN}" --region "${REGION}"
fi

echo "Teardown complete."
