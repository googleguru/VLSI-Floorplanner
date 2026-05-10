# CA-Floorplanner Docker image
# Provides: Python 3.11, required Python packages, OpenROAD (if available in PATH)
# OpenROAD is NOT installed here by default — mount or install separately.
# To use a pre-built OpenROAD binary, extend this image:
#   FROM ca-floorplanner:latest
#   RUN apt-get install -y openroad   # or COPY a static binary

FROM python:3.11-slim

LABEL maintainer="R.Pavithra Guru"
LABEL description="Rule-Based CA Floorplanner for VLSI Physical Design"

# ── system deps ───────────────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        yosys \
        git \
        curl \
        libgl1 \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# ── workdir ───────────────────────────────────────────────────────────────────
WORKDIR /workspace

# ── Python deps ───────────────────────────────────────────────────────────────
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── copy source ───────────────────────────────────────────────────────────────
COPY . .
RUN pip install --no-cache-dir -e .

# ── output dir ────────────────────────────────────────────────────────────────
RUN mkdir -p outputs/figures outputs/floorplans outputs/tables \
             outputs/logs outputs/reports

# ── entrypoint ────────────────────────────────────────────────────────────────
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENV PYTHONUNBUFFERED=1

ENTRYPOINT ["/entrypoint.sh"]
CMD ["--help"]
