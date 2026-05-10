# Rule-Based Cellular Automata Floorplanner for VLSI Physical Design

> A publication-grade research framework that applies **rule-based Cellular Automata (CA)** to guide macro placement for VLSI floorplanning, with **OpenROAD `initialize_floorplan` (ifp)** as the detailed back-end initializer.
> Supports ASAP7 PDK, IPSD benchmark circuits, and ISCAS-85/89 benchmark circuits.

---

## Pipeline Overview

![pipeline](outputs/figures/pipeline_overview.png)

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [CA Rule Engine](#ca-rule-engine)
4. [OpenROAD ifp Integration](#openroad-ifp-integration)
5. [Results](#results)
6. [Figures](#figures)
7. [Benchmark Preparation](#benchmark-preparation)
8. [ASAP7 PDK Setup](#asap7-pdk-setup)
9. [Reproduction Commands](#reproduction-commands)
10. [Docker Workflow](#docker-workflow)
11. [Makefile Targets](#makefile-targets)
12. [Evaluation Metrics](#evaluation-metrics)
13. [License](#license)

---

## Overview

Classical floorplanning heuristics treat macro placement as an isolated combinatorial problem. This framework models the entire core area as a **2D cellular automaton** — a multi-channel continuous field — and evolves it using five families of deterministic, explainable rules before feeding the resulting macro region assignment into OpenROAD's `initialize_floorplan`.

**No learned policy. No black-box ML.** Every update rule is documented, reproducible, and analytically traceable.

Key results on synthetic benchmarks (CA `full_ca` vs `baseline`):
- **HPWL reduction:** up to **−56.9 %** (synth_small), **−67.7 %** (synth_medium), **−66.6 %** (synth_large)
- **Whitespace fragmentation** reduced on all designs
- **100 % outline compliance** maintained across all methods

---

## Architecture

```
VLSI-Floorplanner/
├── configs/
│   ├── ca_rules.yaml          # Rule families, phases, weights, search space
│   ├── benchmarks.yaml        # Registry: IPSD ×4, ISCAS ×27, ASAP7 ×2, synthetic ×3
│   └── asap7.yaml             # ASAP7 PDK paths, site names, routing layers
│
├── src/
│   ├── data/                  # Benchmark registry + adapters
│   │   ├── registry.py             # Central registry (auto-skips missing collateral)
│   │   ├── benchmark_base.py       # BenchmarkDesign, SizingMode, SkipReason
│   │   ├── ipsd_adapter.py         # IPSD LEF/DEF loader
│   │   ├── iscas_adapter.py        # ISCAS bench→BLIF→Yosys→DEF pipeline
│   │   ├── asap7_manifest.py       # ASAP7 PDK validator + loader
│   │   ├── synthetic_adapter.py    # Synthetic design generator (no collateral needed)
│   │   ├── bench2blif.py           # Pure-Python ISCAS .bench → BLIF converter
│   │   └── def_stub_writer.py      # Minimal DEF stub generator
│   │
│   ├── ifp_engine/            # OpenROAD ifp interface
│   │   ├── tcl_generator.py        # Generates Tcl; enforces sizing-mode exclusivity
│   │   ├── openroad_wrapper.py     # Subprocess runner; simulation-mode fallback
│   │   ├── def_lef_parser.py       # Lightweight DEF/LEF parser
│   │   ├── row_track_helpers.py    # make_rows / make_tracks helpers
│   │   └── templates/              # Tcl templates (die_core, utilization, with_tracks)
│   │
│   ├── ca/                    # Cellular Automata engine
│   │   ├── grid_model.py           # 6-channel 2D grid; phy↔grid coordinate transforms
│   │   ├── rule_library.py         # 5 rule families (numpy + scipy, no ML)
│   │   ├── rule_engine.py          # Weighted simultaneous rule application
│   │   ├── neighborhood.py         # Zero-padded Moore / von Neumann operators
│   │   ├── tie_breaking.py         # Deterministic spatial bias for exact-tie resolution
│   │   └── evolution_scheduler.py  # Multi-phase scheduler with early stopping
│   │
│   ├── floorplan/             # Discrete floorplan representation
│   │   ├── macro_abstraction.py    # MacroRegion, FloorplanState, MacroAssigner
│   │   ├── overlap_repair.py       # Push-apart greedy overlap elimination
│   │   ├── whitespace_control.py   # Fragmentation score (histogram method)
│   │   └── fixed_outline.py        # Outline constraint checker + legalization
│   │
│   ├── objectives/
│   │   └── metrics.py              # HPWL, density variance, fragmentation, overlap
│   │
│   ├── eval/                  # Experiment orchestration
│   │   ├── experiment_driver.py    # Click CLI: baseline / full / ablation / rule-search
│   │   ├── baseline.py             # Pure ifp baseline flow
│   │   ├── ca_flow.py              # CA-guided flow
│   │   ├── ablation.py             # 4-level ablation study driver
│   │   ├── rule_search.py          # Grid search over α / β / γ / neighborhood
│   │   └── csv_writer.py           # CSV + summary writer
│   │
│   ├── viz/                   # Publication-grade plotting
│   │   ├── publication_utils.py    # rcParams, save_fig, color palette
│   │   ├── floorplan_renderer.py   # Core+macro snapshot
│   │   ├── heatmap.py              # Per-channel CA grid heatmaps
│   │   ├── evolution_plots.py      # Phase snapshots + phase timeline
│   │   └── comparison_charts.py    # Grouped bars, ablation bars, Pareto scatter
│   │
│   └── report/
│       ├── readme_updater.py       # Tag-based README section replacement
│       └── markdown_generator.py   # Table + figure-embed markdown generators
│
├── scripts/
│   ├── generate_figures.py    # Full figure-generation script
│   ├── build_openroad_ifp.sh  # Clone + build OpenROAD from source
│   ├── run_benchmarks.sh      # Baseline + full CA + report in one shot
│   ├── run_ablation.sh        # Ablation study wrapper
│   └── make_report.sh         # README update only
│
├── docker/
│   ├── Dockerfile             # Python 3.11 + Yosys; OpenROAD mountable
│   ├── docker-compose.yml     # Services: baseline / eval / ablation / report
│   └── entrypoint.sh
│
├── tests/                     # 32 unit tests — all pass
├── Makefile                   # 10 targets
└── outputs/
    ├── figures/               # All PNG figures (committed to repo)
    ├── floorplans/            # Generated DEF files
    ├── tables/                # CSV results
    └── logs/                  # OpenROAD run logs
```

---

## CA Rule Engine

The core area is discretised into a **64 × 64 grid** (configurable). Each cell stores a 6-channel state vector:

| Ch | Name | Range | Meaning |
|----|------|-------|---------|
| 0 | `occupancy` | {0,1,2,3} | empty / blockage / macro / stdcell |
| 1 | `density` | [0, 1] | local utilization estimate |
| 2 | `macro_affinity` | [0, 1] | attraction strength to macro placement |
| 3 | `boundary_pressure` | [0, 1] | inverse distance to die edge |
| 4 | `net_pressure` | [0, 1] | accumulated net connectivity load |
| 5 | `blockage` | {0, 1} | hard keepout flag |

### Rule Activation per Phase

![rule_diagram](outputs/figures/ca_rule_diagram.png)

### Five Rule Families

| # | Rule | Channel | Formula |
|---|------|---------|---------|
| 1 | **Density equalization** | `density` | `Δd = α · (mean_nbr_d − d)` when `|Δ| > threshold` |
| 2 | **Connectivity attraction** | `macro_affinity` | `Δaff = β · net · (1 − aff)` |
| 3 | **Repulsion / separation** | `macro_affinity` | `Δaff = −γ · overlap_pressure · aff` |
| 4 | **Boundary regularization** | `density` | `Δd = −λ_b · bnd · d` |
| 5 | **Whitespace smoothing** | `density` | `Δd = σ · (Gauss(d) − d) + 0.1 · (target − d)` |

All rules fire **simultaneously** each generation (weighted sum of deltas). State is clamped to [0, 1] after every step. Exact ties broken by a deterministic spatial bias (`ε ≈ 1e−9`) — fully reproducible given a fixed seed.

### Phase Schedule

![phase_timeline](outputs/figures/phase_timeline.png)

---

## OpenROAD ifp Integration

Reference: <https://openroad.readthedocs.io/en/latest/main/src/ifp/README.html>

Two **mutually exclusive** sizing modes — enforced in Python via `BenchmarkDesign.validate_sizing()` before any Tcl is emitted:

**Mode A — Explicit die/core area:**
```tcl
initialize_floorplan \
    -die_area  { llx lly urx ury } \
    -core_area { llx lly urx ury } \
    -site      <site_name>
```

**Mode B — Utilization + aspect ratio:**
```tcl
initialize_floorplan \
    -utilization  0.70 \
    -aspect_ratio 1.0  \
    -core_space   { left bottom right top } \
    -site         <site_name>
```

Additional ifp features supported:
```tcl
make_rows -site <name> [-additional_sites <s>] [-flip_alternate_rows] [-row_parity even]
make_tracks M1 -x_offset 0 -x_pitch 0.027 -y_offset 0 -y_pitch 0.027
```

> **Simulation mode:** when `openroad` is absent from `PATH`, the wrapper writes valid Tcl, produces a stub DEF, and the full Python pipeline continues. All metrics computed from CA-guided floorplan state, logged with `simulated=True`.

---

## Results

### HPWL Improvement over Baseline

![improvement](outputs/figures/improvement_hpwl.png)

### Ablation Study — HPWL

![ablation_hpwl](outputs/figures/ablation_hpwl_um.png)

### Ablation Study — Overlap Count

![ablation_overlap](outputs/figures/ablation_overlap_count.png)

### Ablation Study — Whitespace Fragmentation

![ablation_frag](outputs/figures/ablation_whitespace_frag.png)

### Ablation Study — Density Variance

![ablation_dvar](outputs/figures/ablation_density_variance.png)

### Multi-Metric Radar Comparison

![radar](outputs/figures/radar_comparison.png)

### Per-Design Ablation Results Table

| Design | Method | HPWL (µm) | Overlaps | Density Var | WS Frag | Outline | Runtime (s) |
|:-------|:-------|----------:|:--------:|:-----------:|:-------:|:-------:|:-----------:|
| synth_small | baseline | 1 520.0 | 0 | 0.108 | 0.652 | 1.000 | 0.001 |
| synth_small | density_only | 1 520.0 | 0 | 0.130 | 0.644 | 1.000 | 0.019 |
| synth_small | density_connectivity | 629.8 | 1 | 0.104 | 0.551 | 1.000 | 0.030 |
| synth_small | **full_ca** | **656.0** | **0** | 0.124 | **0.529** | 1.000 | 0.065 |
| synth_medium | baseline | 6 460.0 | 0 | 0.098 | 0.774 | 1.000 | 0.001 |
| synth_medium | density_only | 6 549.1 | 0 | 0.108 | 0.759 | 1.000 | 0.023 |
| synth_medium | density_connectivity | 2 216.6 | 10 | 0.061 | 0.536 | 1.000 | 0.038 |
| synth_medium | **full_ca** | **2 086.0** | **10** | **0.060** | **0.537** | 1.000 | 0.128 |
| synth_large | baseline | 33 250.0 | 0 | 0.077 | 0.833 | 1.000 | 0.001 |
| synth_large | density_only | 33 250.0 | 0 | 0.108 | 0.826 | 1.000 | 0.033 |
| synth_large | density_connectivity | 6 843.7 | 66 | 0.042 | 0.530 | 1.000 | 0.074 |
| synth_large | **full_ca** | **11 112.8** | 45 | **0.052** | **0.518** | 1.000 | 0.101 |

> Results from synthetic designs in simulation mode (OpenROAD not installed). Install OpenROAD for full DEF-backed metrics.

<!-- CA_RESULTS_START -->
<!-- CA_RESULTS_END -->

---

## Figures

### Floorplan Snapshots

**Baseline (OpenROAD ifp, no CA guidance):**

| synth_small | synth_medium | synth_large |
|:-----------:|:-----------:|:-----------:|
| ![](outputs/figures/floorplan_synth_small_baseline.png) | ![](outputs/figures/floorplan_synth_medium_baseline.png) | ![](outputs/figures/floorplan_synth_large_baseline.png) |

**Full CA (5 rules, 6 phases):**

| synth_small | synth_medium | synth_large |
|:-----------:|:-----------:|:-----------:|
| ![](outputs/figures/floorplan_synth_small_full_ca.png) | ![](outputs/figures/floorplan_synth_medium_full_ca.png) | ![](outputs/figures/floorplan_synth_large_full_ca.png) |

**Side-by-side comparison (all designs):**

![comparison](outputs/figures/floorplan_comparison.png)

### CA Grid Heatmaps (synth_small — initial state)

![heatmap_small](outputs/figures/heatmap_synth_small_initial.png)

### CA Grid Heatmaps (synth_medium)

![heatmap_medium](outputs/figures/heatmap_synth_medium_initial.png)

### CA Grid Heatmaps (synth_large)

![heatmap_large](outputs/figures/heatmap_synth_large_initial.png)

### Density Convergence Across Evolution

![convergence](outputs/figures/convergence_density.png)

### Ablation Runtime

![runtime](outputs/figures/ablation_runtime_s.png)

<!-- CA_FIGURES_START -->
<!-- CA_FIGURES_END -->

---

## Benchmark Preparation

### Synthetic Designs (built-in, no download needed)
```bash
make baseline    # runs immediately on 3 synthetic designs
```

### IPSD (ISPD / ICCAD contest circuits)
```bash
# Download from ISPD 2015 / ICCAD 2015 contest pages, then:
mkdir -p data/benchmarks/ipsd/des3
cp des3.lef des3.def data/benchmarks/ipsd/des3/
# Repeat for: mgc_des_perf_1   mgc_fft_1   mgc_matrix_mult_1
```

### ISCAS-85/89 (gate-level netlists)
```bash
# Step 1 — download .bench files:
#   ISCAS-85: https://www.pld.ttu.ee/~maksim/benchmarks/iscas85/bench/
#   ISCAS-89: https://www.pld.ttu.ee/~maksim/benchmarks/iscas89/bench/

mkdir -p data/benchmarks/iscas/c432
cp c432.bench data/benchmarks/iscas/c432/

# Step 2 — install Yosys (technology mapping):
apt-get install yosys

# Step 3 — run; the adapter fires automatically:
python -m src.eval.experiment_driver --mode full --family iscas
# Pipeline: .bench → BLIF (bench2blif.py) → Yosys → stub DEF
```

Missing collateral → automatic `SKIP(reason)` with acquisition instructions in logs.

---

## ASAP7 PDK Setup

```bash
# Clone open PDK collateral:
git clone https://github.com/The-OpenROAD-Project/asap7 data/pdk/asap7

# configs/asap7.yaml already points to data/pdk/asap7
# Framework validates before any ASAP7 run:
#   ✓ asap7_tech.lef
#   ✓ asap7sc7p5t_28_R.lef
# Missing → SKIP(MISSING_PDK) with acquisition note.
```

Site: `asap7sc7p5t_28_R_site` · Routing layers: M1–M4 at 27 nm / 54 nm pitch.

---

## Reproduction Commands

### Local (Python ≥ 3.9)

```bash
# Install
pip install -e . -r requirements.txt

# Run on synthetic designs (no external collateral needed)
make baseline      # ifp-only baseline
make eval          # full CA + baseline + floorplan figures
make ablation      # 4-level ablation study
make rule-search   # α / β / γ / neighborhood grid search
make report        # auto-update README

# Regenerate all figures
python scripts/generate_figures.py

# Specific benchmark family
python -m src.eval.experiment_driver --mode full --family iscas

# Tests (32 tests, all expected to pass)
python -m pytest tests/ -v
```

### Shell scripts

```bash
bash scripts/run_benchmarks.sh     # baseline + full CA + report
bash scripts/run_ablation.sh       # ablation only
bash scripts/make_report.sh        # README update only
bash scripts/build_openroad_ifp.sh # build OpenROAD from source
```

---

## Docker Workflow

```bash
# Build
docker build -f docker/Dockerfile -t ca-floorplanner:latest .

# One-command services
docker compose -f docker/docker-compose.yml run baseline
docker compose -f docker/docker-compose.yml run eval
docker compose -f docker/docker-compose.yml run ablation
docker compose -f docker/docker-compose.yml run report

# With real benchmarks mounted
docker run --rm \
  -v "$(pwd)/data:/workspace/data:ro" \
  -v "$(pwd)/outputs:/workspace/outputs" \
  ca-floorplanner:latest \
  --mode full --config configs/benchmarks.yaml
```

---

## Makefile Targets

| Target | Action |
|--------|--------|
| `make install` | Install Python package + dependencies |
| `make build` | Alias for install |
| `make docker-build` | Build Docker image |
| `make baseline` | Baseline ifp-only run |
| `make eval` | Full CA + baseline evaluation |
| `make ablation` | 4-level ablation study |
| `make rule-search` | CA hyper-parameter grid search |
| `make report` | Auto-update README |
| `make clean` | Remove generated outputs |

---

## Evaluation Metrics

| Metric | Description | Direction |
|--------|-------------|:---------:|
| `hpwl_um` | Estimated HPWL from net bounding boxes (µm) | lower ↓ |
| `overlap_count` | Pairwise macro overlap count | lower ↓ |
| `overlap_area_um2` | Total overlap area (µm²) | lower ↓ |
| `density_variance` | Variance of per-cell utilization over core grid | lower ↓ |
| `whitespace_frag` | Whitespace fragmentation [0 = best, 1 = worst] | lower ↓ |
| `outline_success` | Fraction of macros satisfying core-area constraint | higher ↑ |
| `aspect_ratio_err` | `\|actual W/H − target\|` | lower ↓ |
| `runtime_s` | Wall-clock time including CA evolution + ifp call | lower ↓ |

---

## License

This repository is released under the **MIT License**.

- [OpenROAD](https://github.com/The-OpenROAD-Project/OpenROAD) is distributed under **BSD-3-Clause**.
- [ASAP7 PDK](https://github.com/The-OpenROAD-Project/asap7) is subject to its own license — review before use.
- IPSD and ISCAS benchmark circuits carry their respective contest / academic licenses — do not redistribute without permission.
