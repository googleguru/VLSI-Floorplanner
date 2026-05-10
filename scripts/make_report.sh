#!/usr/bin/env bash
# Generate report: update README with latest results and figures.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "${REPO_ROOT}"

OUTPUT="${1:-outputs}"

echo "=== Generating Report ==="

python -m src.report.readme_updater \
    --results "${OUTPUT}/tables" \
    --figures "${OUTPUT}/figures" \
    --readme README.md

echo "README.md updated."
