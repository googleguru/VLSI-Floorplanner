#!/usr/bin/env bash
# Run the full evaluation pipeline for all available benchmarks.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "${REPO_ROOT}"

CONFIG="${1:-configs/benchmarks.yaml}"
CA_CONFIG="${2:-configs/ca_rules.yaml}"
OUTPUT="${3:-outputs}"
FAMILY="${4:-}"   # optional: filter to one family

FAMILY_ARG=""
if [[ -n "${FAMILY}" ]]; then
    FAMILY_ARG="--family ${FAMILY}"
fi

echo "=== CA-Floorplanner: Full Benchmark Evaluation ==="
echo "Config     : ${CONFIG}"
echo "CA Config  : ${CA_CONFIG}"
echo "Output dir : ${OUTPUT}"
echo ""

# 1. Baseline
echo "--- [1/3] Baseline ---"
python -m src.eval.experiment_driver \
    --mode baseline \
    --config "${CONFIG}" \
    --ca-config "${CA_CONFIG}" \
    --output "${OUTPUT}" \
    ${FAMILY_ARG}

# 2. Full CA evaluation
echo "--- [2/3] Full CA ---"
python -m src.eval.experiment_driver \
    --mode full \
    --config "${CONFIG}" \
    --ca-config "${CA_CONFIG}" \
    --output "${OUTPUT}" \
    ${FAMILY_ARG}

# 3. Report
echo "--- [3/3] Report ---"
python -m src.report.readme_updater \
    --results "${OUTPUT}/tables" \
    --figures "${OUTPUT}/figures" \
    --readme README.md

echo ""
echo "=== Done. Results in ${OUTPUT} ==="
