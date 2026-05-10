#!/usr/bin/env bash
# Build OpenROAD from source (ifp-capable build).
# Reference: https://openroad.readthedocs.io/en/latest/main/README.html
#
# Prerequisites: cmake ≥ 3.14, gcc/g++ ≥ 9, Tcl 8.6, SWIG 4.
# This script clones and builds only if openroad is not already on PATH.

set -euo pipefail

OPENROAD_TAG="${OPENROAD_TAG:-v2.0-8156}"
INSTALL_DIR="${INSTALL_DIR:-/usr/local}"
BUILD_DIR="${BUILD_DIR:-/tmp/openroad_build}"

if command -v openroad &>/dev/null; then
    echo "[INFO] openroad already on PATH: $(which openroad)"
    openroad -version 2>/dev/null || true
    exit 0
fi

echo "[INFO] Building OpenROAD ${OPENROAD_TAG} ..."

# Install build deps (Debian/Ubuntu)
apt-get update -qq
apt-get install -y --no-install-recommends \
    cmake ninja-build \
    libboost-all-dev libeigen3-dev \
    swig python3-dev \
    tcl8.6-dev libffi-dev \
    flex bison \
    libreadline-dev \
    git ca-certificates

git clone --depth 1 --branch "${OPENROAD_TAG}" \
    https://github.com/The-OpenROAD-Project/OpenROAD.git \
    "${BUILD_DIR}"

cd "${BUILD_DIR}"
git submodule update --init --recursive

mkdir -p build && cd build
cmake .. \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_INSTALL_PREFIX="${INSTALL_DIR}" \
    -GNinja

ninja -j"$(nproc)"
ninja install

echo "[INFO] OpenROAD installed at ${INSTALL_DIR}/bin/openroad"
openroad -version
