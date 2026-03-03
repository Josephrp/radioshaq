#!/bin/bash
# Main deployment script for RadioShaq to AWS
# Usage: ./deploy.sh [environment] [region]
# Example: ./deploy.sh production us-east-1

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AWS_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
ENVIRONMENT="${1:-staging}"
REGION="${2:-us-east-1}"
STACK_NAME="radioshaq-${ENVIRONMENT}"

echo "Deploying RadioShaq to ${ENVIRONMENT} in ${REGION}"

# 1. Build Lambda layers (optional; create if not present)
if [ -f "${SCRIPT_DIR}/build_layers.sh" ]; then
  echo "Building Lambda layers..."
  "${SCRIPT_DIR}/build_layers.sh" "${ENVIRONMENT}" "${REGION}"
fi

# 2. Deploy base infrastructure (VPC, security groups)
if [ -f "${AWS_DIR}/cloudformation/base.yaml" ]; then
  echo "Deploying base infrastructure..."
  aws cloudformation deploy \
    --template-file "${AWS_DIR}/cloudformation/base.yaml" \
    --stack-name "${STACK_NAME}-base" \
    --region "${REGION}" \
    --capabilities CAPABILITY_IAM \
    --parameter-overrides Environment="${ENVIRONMENT}"
fi

# 3. Deploy database (DynamoDB)
if [ -f "${AWS_DIR}/cloudformation/database.yaml" ]; then
  echo "Deploying databases..."
  aws cloudformation deploy \
    --template-file "${AWS_DIR}/cloudformation/database.yaml" \
    --stack-name "${STACK_NAME}-db" \
    --region "${REGION}" \
    --capabilities CAPABILITY_IAM \
    --parameter-overrides Environment="${ENVIRONMENT}"
fi

# 4. Deploy Lambda (needs table ARNs from database stack)
if [ -f "${AWS_DIR}/cloudformation/lambda.yaml" ]; then
  echo "Deploying Lambda functions..."
  LAMBDA_PARAMS="Environment=${ENVIRONMENT}"
  if aws cloudformation describe-stacks --stack-name "${STACK_NAME}-db" --region "${REGION}" 2>/dev/null; then
    STATE_ARN=$(aws cloudformation describe-stacks --stack-name "${STACK_NAME}-db" --query "Stacks[0].Outputs[?OutputKey=='StateTableArn'].OutputValue" --output text --region "${REGION}" 2>/dev/null || true)
    SESS_ARN=$(aws cloudformation describe-stacks --stack-name "${STACK_NAME}-db" --query "Stacks[0].Outputs[?OutputKey=='SessionsTableArn'].OutputValue" --output text --region "${REGION}" 2>/dev/null || true)
    [ -n "${STATE_ARN}" ] && LAMBDA_PARAMS="${LAMBDA_PARAMS} StateTableArn=${STATE_ARN}"
    [ -n "${SESS_ARN}" ] && LAMBDA_PARAMS="${LAMBDA_PARAMS} SessionsTableArn=${SESS_ARN}"
  fi
  aws cloudformation deploy \
    --template-file "${AWS_DIR}/cloudformation/lambda.yaml" \
    --stack-name "${STACK_NAME}-lambda" \
    --region "${REGION}" \
    --capabilities CAPABILITY_IAM \
    --parameter-overrides ${LAMBDA_PARAMS}
  # Update Lambda code from zip
  if [ -f "${SCRIPT_DIR}/deploy_lambda.sh" ]; then
    "${SCRIPT_DIR}/deploy_lambda.sh" "${ENVIRONMENT}" "${REGION}"
  fi
fi

# 5. Deploy API Gateway (needs API handler ARN from Lambda stack)
if [ -f "${AWS_DIR}/cloudformation/api_gateway.yaml" ]; then
  echo "Deploying API Gateway..."
  API_PARAMS="Environment=${ENVIRONMENT}"
  if aws cloudformation describe-stacks --stack-name "${STACK_NAME}-lambda" --region "${REGION}" 2>/dev/null; then
    API_ARN=$(aws cloudformation describe-stacks --stack-name "${STACK_NAME}-lambda" --query "Stacks[0].Outputs[?OutputKey=='ApiHandlerFunctionArn'].OutputValue" --output text --region "${REGION}" 2>/dev/null || true)
    [ -n "${API_ARN}" ] && API_PARAMS="${API_PARAMS} ApiHandlerFunctionArn=${API_ARN}"
  fi
  aws cloudformation deploy \
    --template-file "${AWS_DIR}/cloudformation/api_gateway.yaml" \
    --stack-name "${STACK_NAME}-api" \
    --region "${REGION}" \
    --capabilities CAPABILITY_IAM \
    --parameter-overrides ${API_PARAMS}
fi

# 6. Deploy Step Functions (REACT orchestrator)
if [ -f "${AWS_DIR}/stepfunctions/react_orchestrator.asl.json" ]; then
  echo "Deploying Step Functions..."
  ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
  ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/${STACK_NAME}-stepfunctions-role"
  STATE_MACHINE_ARN="arn:aws:states:${REGION}:${ACCOUNT_ID}:stateMachine:${STACK_NAME}-orchestrator"
  if aws stepfunctions describe-state-machine --state-machine-arn "${STATE_MACHINE_ARN}" --region "${REGION}" 2>/dev/null; then
    aws stepfunctions update-state-machine \
      --state-machine-arn "${STATE_MACHINE_ARN}" \
      --definition "file://${AWS_DIR}/stepfunctions/react_orchestrator.asl.json" \
      --region "${REGION}"
  else
    aws stepfunctions create-state-machine \
      --name "${STACK_NAME}-orchestrator" \
      --definition "file://${AWS_DIR}/stepfunctions/react_orchestrator.asl.json" \
      --role-arn "${ROLE_ARN}" \
      --region "${REGION}"
  fi
fi

echo "Deployment complete."
if aws cloudformation describe-stacks --stack-name "${STACK_NAME}-api" --region "${REGION}" 2>/dev/null; then
  API_ENDPOINT=$(aws cloudformation describe-stacks --stack-name "${STACK_NAME}-api" --query 'Stacks[0].Outputs[?OutputKey==`ApiEndpoint`].OutputValue' --output text --region "${REGION}" 2>/dev/null || true)
  [ -n "${API_ENDPOINT}" ] && echo "API Endpoint: ${API_ENDPOINT}"
fi
