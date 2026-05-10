#!/usr/bin/env bash
# Run ablation study across all available benchmark designs.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "${REPO_ROOT}"

CONFIG="${1:-configs/benchmarks.yaml}"
CA_CONFIG="${2:-configs/ca_rules.yaml}"
OUTPUT="${3:-outputs}"

echo "=== CA-Floorplanner: Ablation Study ==="

python -m src.eval.experiment_driver \
    --mode ablation \
    --config "${CONFIG}" \
    --ca-config "${CA_CONFIG}" \
    --output "${OUTPUT}"

python -m src.report.readme_updater \
    --results "${OUTPUT}/tables" \
    --figures "${OUTPUT}/figures" \
    --readme README.md

echo "Ablation complete. Results in ${OUTPUT}/tables/"
