.PHONY: build docker-build baseline eval ablation report clean install

PYTHON      := python3
SCRIPTS     := scripts
SRC         := src
OUTPUT      := outputs
DOCKER_TAG  := ca-floorplanner:latest

# ── local install ─────────────────────────────────────────────────────────────
install:
	pip install -e . -r requirements.txt

# ── docker ───────────────────────────────────────────────────────────────────
build: install

docker-build:
	docker build -f docker/Dockerfile -t $(DOCKER_TAG) .

docker-run:
	docker compose -f docker/docker-compose.yml up --build

# ── experiment targets ────────────────────────────────────────────────────────
baseline:
	$(PYTHON) -m src.eval.experiment_driver \
	    --mode baseline \
	    --config configs/benchmarks.yaml \
	    --output $(OUTPUT)

eval:
	$(PYTHON) -m src.eval.experiment_driver \
	    --mode full \
	    --config configs/benchmarks.yaml \
	    --ca-config configs/ca_rules.yaml \
	    --output $(OUTPUT)

ablation:
	$(PYTHON) -m src.eval.experiment_driver \
	    --mode ablation \
	    --config configs/benchmarks.yaml \
	    --ca-config configs/ca_rules.yaml \
	    --output $(OUTPUT)

rule-search:
	$(PYTHON) -m src.eval.experiment_driver \
	    --mode rule-search \
	    --config configs/benchmarks.yaml \
	    --ca-config configs/ca_rules.yaml \
	    --output $(OUTPUT)

report:
	$(PYTHON) -m src.report.readme_updater \
	    --results $(OUTPUT)/tables \
	    --figures $(OUTPUT)/figures \
	    --readme README.md

# ── shell scripts (alternative) ───────────────────────────────────────────────
run-benchmarks:
	bash $(SCRIPTS)/run_benchmarks.sh

run-ablation:
	bash $(SCRIPTS)/run_ablation.sh

make-report:
	bash $(SCRIPTS)/make_report.sh

# ── housekeeping ─────────────────────────────────────────────────────────────
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; \
	rm -f $(OUTPUT)/figures/*.png $(OUTPUT)/figures/*.pdf \
	      $(OUTPUT)/tables/*.csv \
	      $(OUTPUT)/logs/*.log \
	      $(OUTPUT)/reports/*.md \
	      $(OUTPUT)/floorplans/*.def
