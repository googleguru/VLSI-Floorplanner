#!/usr/bin/env bash
# Docker entrypoint for CA-Floorplanner
# Passes all arguments to the experiment driver CLI.
set -euo pipefail

echo "=== CA-Floorplanner ==="
echo "Mode: ${1:-help}"
echo "========================"

exec python -m src.eval.experiment_driver "$@"
