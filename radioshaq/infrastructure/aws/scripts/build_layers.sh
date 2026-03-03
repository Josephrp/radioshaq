#!/bin/bash
# Build Lambda layers for RadioShaq (optional - used if deploy.sh runs this)
# Usage: ./build_layers.sh [environment] [region]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AWS_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
BUILD_DIR="${AWS_DIR}/build"
LAYER_ZIP="${BUILD_DIR}/layer.zip"

mkdir -p "${BUILD_DIR}"
echo "Lambda layers: no custom layer required for default deploy (deps bundled in lambda.zip)."
echo "To add a shared layer (e.g. aws-lambda-powertools), package it and upload to S3."
touch "${LAYER_ZIP}" 2>/dev/null || true
echo "Done."
