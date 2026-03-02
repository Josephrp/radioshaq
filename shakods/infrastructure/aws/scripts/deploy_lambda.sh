#!/bin/bash
# Deploy SHAKODS Lambda functions (API handler, message handler)
# Usage: ./deploy_lambda.sh [environment] [region]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AWS_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
SHAKODS_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
ENVIRONMENT="${1:-staging}"
REGION="${2:-us-east-1}"
STACK_NAME="shakods-${ENVIRONMENT}"
LAMBDA_DIR="${AWS_DIR}/lambda"
OUTPUT_ZIP="${AWS_DIR}/build/lambda.zip"

mkdir -p "${AWS_DIR}/build"
cd "${SHAKODS_ROOT}"

# Build deployment package: shakods package + lambda handlers + dependencies
echo "Building Lambda deployment package..."
rm -f "${OUTPUT_ZIP}"

# Create a staging dir to avoid polluting repo
STAGING="${AWS_DIR}/build/staging"
rm -rf "${STAGING}"
mkdir -p "${STAGING}"

# Install shakods and dependencies into staging (use pip with target)
pip install --target "${STAGING}" . -q 2>/dev/null || uv pip install --target "${STAGING}" . -q 2>/dev/null || true

# Copy Lambda handler modules into package
mkdir -p "${STAGING}/infrastructure/aws/lambda"
cp -r "${LAMBDA_DIR}"/*.py "${STAGING}/infrastructure/aws/lambda/" 2>/dev/null || true

# Zip (from staging so package layout is correct)
cd "${STAGING}"
zip -rq "${OUTPUT_ZIP}" .
cd "${SHAKODS_ROOT}"

# Get Lambda function names from CloudFormation if stack exists
API_FUNCTION_NAME="${STACK_NAME}-api-handler"
MESSAGE_FUNCTION_NAME="${STACK_NAME}-message-handler"

if aws cloudformation describe-stacks --stack-name "${STACK_NAME}-lambda" --region "${REGION}" 2>/dev/null; then
  API_FUNCTION_NAME=$(aws cloudformation describe-stacks --stack-name "${STACK_NAME}-lambda" --query "Stacks[0].Outputs[?OutputKey=='ApiHandlerFunctionName'].OutputValue" --output text --region "${REGION}" 2>/dev/null || echo "${API_FUNCTION_NAME}")
  MESSAGE_FUNCTION_NAME=$(aws cloudformation describe-stacks --stack-name "${STACK_NAME}-lambda" --query "Stacks[0].Outputs[?OutputKey=='MessageHandlerFunctionName'].OutputValue" --output text --region "${REGION}" 2>/dev/null || echo "${MESSAGE_FUNCTION_NAME}")
fi

# Update Lambda code (and handler) if functions exist
if aws lambda get-function --function-name "${API_FUNCTION_NAME}" --region "${REGION}" 2>/dev/null; then
  echo "Updating API handler: ${API_FUNCTION_NAME}"
  aws lambda update-function-code --function-name "${API_FUNCTION_NAME}" --zip-file "fileb://${OUTPUT_ZIP}" --region "${REGION}"
  aws lambda update-function-configuration --function-name "${API_FUNCTION_NAME}" --handler "infrastructure.aws.lambda.api_handler.lambda_handler" --region "${REGION}" 2>/dev/null || true
fi
if aws lambda get-function --function-name "${MESSAGE_FUNCTION_NAME}" --region "${REGION}" 2>/dev/null; then
  echo "Updating message handler: ${MESSAGE_FUNCTION_NAME}"
  aws lambda update-function-code --function-name "${MESSAGE_FUNCTION_NAME}" --zip-file "fileb://${OUTPUT_ZIP}" --region "${REGION}"
  aws lambda update-function-configuration --function-name "${MESSAGE_FUNCTION_NAME}" --handler "infrastructure.aws.lambda.message_handler.lambda_handler" --region "${REGION}" 2>/dev/null || true
fi

echo "Lambda deployment package built: ${OUTPUT_ZIP}"
echo "Deploy CloudFormation stack ${STACK_NAME}-lambda to create/update functions, or update code above."
