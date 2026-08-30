# VLSI-Floorplanner: Reproducibility and Parameter Configuration Guide

## 1. Overview

This guide documents all parameters, configuration options, and best practices for reproducing CA-floorplanner results. The method is **deterministic** given identical input configurations and random seeds.

## 2. Quick Start: Default Configuration

The default configuration achieves good balance across all objectives:

```bash
python -m src.eval.experiment_driver \
  --mode full \
  --config configs/benchmarks.yaml \
  --ca-config configs/ca_rules.yaml \
  --seed 42
```

This runs the **full_ca** rule set (all 6 rules in 7 phases) on all ready benchmarks with seed=42.

## 3. Global Configuration Parameters

### 3.1 File: `configs/ca_rules.yaml` → `global` section

```yaml
global:
  seed: 42                    # RNG seed for reproducibility (default 42)
  grid_resolution: 64         # Grid dimension R=C (default 64)
                              # Larger: finer granularity, slower
                              # Smaller: coarser, faster
  neighborhood: "moore"       # "moore" (8-neighbor) or "von_neumann" (4-neighbor)
  max_generations: 200        # Hard upper limit per phase (default 200)
  convergence_eps: 1e-5       # Early stopping threshold (default 1e-5)
                              # Smaller: stricter convergence, more iterations
                              # Larger: looser, fewer iterations
```

### 3.2 Impact on Reproducibility

| Parameter | Change | Impact |
|-----------|--------|--------|
| seed | Different | Different macro placement (but still deterministic) |
| grid_resolution | Different | Different spatial resolution; affects rule behavior |
| neighborhood | Different | Different neighbor topology; affects rule propagation |
| max_generations | Different | May stop prematurely if set too low |
| convergence_eps | Different | May cause early stopping at different points |

**To reproduce published results**: Keep all global parameters identical.

## 4. Rule-Specific Parameters

Each of the 6 rules has tunable hyperparameters in `ca_rules.yaml` → `rule_params`:

### 4.1 Density Equalization

**File**: `rule_params.density_equalization`

```yaml
density_equalization:
  alpha: 0.25         # Fraction of neighbor-center density difference to apply
                      # Range: [0, 1]
                      # Higher: Faster spread, less stable
                      # Lower: Slower, more controlled
  threshold: 0.05     # Minimum density difference to trigger update
                      # Range: [0, 1]
                      # Higher: Only large differences propagate
                      # Lower: More granular updates
```

**Default effect**: Redistributes utilization ~25% per generation toward neighbors if difference > 5%.

### 4.2 Connectivity Attraction

**File**: `rule_params.connectivity_attraction`

```yaml
connectivity_attraction:
  beta: 0.30          # Attraction strength from net pressure
                      # Range: [0, 1]
                      # Higher: Stronger clustering around hot nets
  max_net_pressure: 1.0  # Clamp applied to net_pressure channel
                         # Prevents runaway scaling
```

**Default effect**: Macro affinity increases 30% per generation in high-connectivity regions.

### 4.3 Repulsion/Separation

**File**: `rule_params.repulsion_separation`

```yaml
repulsion_separation:
  gamma: 0.40         # Repulsion strength
                      # Range: [0, 1]
                      # Higher: Aggressive macro spreading
                      # Lower: Gentler separation
```

**Default effect**: Affinity decreases 40% per generation for densely-packed macros.

### 4.4 Boundary Regularization

**File**: `rule_params.boundary_regularization`

```yaml
boundary_regularization:
  lambda_b: 0.35      # Boundary push strength
                      # Range: [0, 1]
                      # Higher: Faster core-ward redistribution
                      # Lower: Slower, looser enforcement
```

**Default effect**: Density at die edges reduces 35% per generation; redistributes inward.

### 4.5 Whitespace Smoothing

**File**: `rule_params.whitespace_smoothing`

```yaml
whitespace_smoothing:
  sigma: 0.6          # Gaussian kernel standard deviation (in cells)
                      # Range: [0.1, 2.0]
                      # Higher: Wider blur, stronger smoothing
                      # Lower: Narrower blur, preserves detail
  target_utilization: 0.70  # Target density level
                            # Range: [0.5, 0.9]
                            # Drives blend toward this utilization
```

**Default effect**: Smooths density via ~0.6-cell Gaussian; blends toward 70% utilization.

### 4.6 Rule 235

**File**: `rule_params.rule_235`

```yaml
rule_235:
  threshold: 0.30     # Density threshold for "active" cells
                      # Range: [0.1, 0.5]
                      # Higher: Requires denser regions to survive
                      # Lower: Preserves sparser regions
  strength: 0.20      # Rate of convergence
                      # Range: [0.1, 0.5]
                      # Higher: Faster island elimination
                      # Lower: Gradual, smoother transitions
  birth_neighbors: 1  # Min live neighbors to trigger cell birth
                      # Range: [0, 8]
                      # Higher: Stricter birth conditions
                      # Lower: More aggressive seeding
  survival_neighbors: 1  # Min live neighbors to survive
                        # Range: [0, 8]
                        # Higher: Isolated cells die sooner
                        # Lower: Allows more isolated regions
```

**Default effect**: Eliminates isolated cells (0 neighbors) and <30% density; seeds births near clusters.

## 5. Phase Configuration

### 5.1 Phase Structure

Each rule set defines a sequence of **phases**, each with its own rule list and duration:

```yaml
rule_sets:
  full_ca:
    enabled: true
    phases:
      - name: seed
        rules: [density_equalization]
        generations: 20
      - name: compact
        rules: [density_equalization, connectivity_attraction]
        generations: 40
      # ... more phases
    weights:
      density_equalization: 1.0
      connectivity_attraction: 1.2
      # ... more weights
```

### 5.2 Phase Semantics

- **name**: Human-readable phase identifier (for logging)
- **rules**: List of rule names to activate (all fire simultaneously per generation)
- **generations**: Number of generations to evolve this phase
  - Phase terminates early if convergence_eps is reached
  - Can manually tune for different designs
- **weights**: Per-rule contribution multiplier
  - Higher weight = stronger rule effect
  - Typical range: [0.5, 2.0]

### 5.3 Predefined Rule Sets

Four rule sets are provided:

#### baseline (Ablation 0)
No CA; pure OpenROAD `initialize_floorplan`.

#### density_only (Ablation 1)
Two phases:
1. seed (30 gen): density_equalization
2. smooth (20 gen): whitespace_smoothing

**Effect**: Spreads macros for uniform density; fast baseline.

#### density_connectivity (Ablation 2)
Three phases:
1. seed (30 gen): density_equalization
2. cluster (40 gen): connectivity_attraction
3. smooth (20 gen): whitespace_smoothing

**Effect**: Combines density and net pressure; moderate complexity.

#### full_ca (Ablation 3 / Main Method)
Seven phases: seed → compact → separate → cluster → rule235_cleanup → legalize → smooth

**Effect**: Full rule composition; best quality but slower.

## 6. Benchmark Configuration

### 6.1 File: `configs/benchmarks.yaml`

Specifies which benchmark families to load:

```yaml
families:
  synthetic:
    designs:
      - name: synth_small
        type: synthetic
        num_macros: 4
        num_stdcells: 500
        # ...
  ipsd:
    path: /path/to/ipsd/designs
    # ...
  iscas:
    path: /path/to/iscas/designs
    # ...
```

### 6.2 Design-Specific Overrides

Some designs support custom parameters:

```yaml
designs:
  - name: csynth_medium
    grid_resolution: 128  # Override for this design
    seed: 99              # Different seed
```

### 6.3 Skipping Designs

Designs are auto-skipped if required files are missing. To manually skip:

```yaml
designs:
  - name: design_name
    enabled: false
```

## 7. Reproducibility Checklist

To reproduce exact published results:

- [ ] **Code version**: Same git commit as publication
- [ ] **Global seed**: Identical (default 42)
- [ ] **Grid resolution**: Identical (default 64)
- [ ] **Neighborhood**: Identical (default "moore")
- [ ] **Rule parameters**: All hyperparameters match publication Table
- [ ] **Phase sequence**: Same phase order and generations
- [ ] **Phase weights**: Identical rule weights
- [ ] **OpenROAD binary**: Same version or compatible version
- [ ] **Benchmark files**: Identical source LEF/DEF/BLIF inputs
- [ ] **Python environment**: Same NumPy, SciPy versions
- [ ] **Platform**: Same OS (Linux/Windows) and architecture (x86/ARM)

## 8. Parameter Sensitivity Analysis

### 8.1 High-Sensitivity Parameters
These significantly affect results:
- **seed**: Changes macro placement entirely
- **grid_resolution**: Affects spatial granularity
- **connectivity_attraction.beta**: Strongly influences clustering
- **rule_235.threshold**: Determines island elimination aggressiveness
- **phase order**: Sequence matters for convergence

### 8.2 Low-Sensitivity Parameters
These have modest effects:
- **density_equalization.alpha**: Within [0.15, 0.35], results are stable
- **convergence_eps**: Early stopping rarely activates with current thresholds
- **whitespace_smoothing.sigma**: Modest effect within [0.4, 0.8]

### 8.3 Tuning Strategy
To optimize for a specific design:
1. **Fix global params** (seed, grid_resolution)
2. **Vary rule_sets** (ablation levels)
3. **If needed, adjust phase durations** (add/remove generations)
4. **Fine-tune specific rule weights** if ablation identifies weak spots
5. **Never change rule implementation** unless fixing bugs

## 9. Standalone Execution (No OpenROAD)

To run the CA without OpenROAD:

```python
from src.ca.grid_model import CAGrid
from src.ca.evolution_scheduler import EvolutionScheduler
from src.floorplan.macro_abstraction import MacroAssigner

# Load config
import yaml
with open("configs/ca_rules.yaml") as f:
    cfg = yaml.safe_load(f)

# Create grid
core = (0, 0, 1000, 1000)  # 1000µm × 1000µm core
grid = CAGrid(rows=64, cols=64, core_area=core, seed=42)

# Seed macros and density (example)
grid.place_macro(10, 10, 5, 5, affinity=0.8)
grid.seed_density(total_area=10000, stdcell_density=0.5)

# Evolve
rule_cfg = cfg["rule_sets"]["full_ca"]
rule_params = cfg["rule_params"]
scheduler = EvolutionScheduler(
    phases=rule_cfg["phases"],
    weights=rule_cfg["weights"],
    rule_params=rule_params,
    neighborhood="moore",
)
evolved_grid, evo_record = scheduler.evolve(grid)

# Extract macro coordinates
assigner = MacroAssigner(affinity_threshold=0.3)
macros = assigner.assign(evolved_grid, design_macros, core)

# Compute metrics
from src.objectives.metrics import compute_metrics
metrics = compute_metrics(macros, core, design.nets)
print(f"HPWL: {metrics.hpwl_um:.1f} µm")
print(f"Overlaps: {metrics.overlap_count}")
```

## 10. Configuration Export and Validation

### 10.1 Export Current Configuration

```bash
python -c "
import yaml
with open('configs/ca_rules.yaml') as f:
    cfg = yaml.safe_load(f)
print(yaml.dump(cfg, default_flow_style=False))
"
```

### 10.2 Validate Configuration

```python
from src.eval.experiment_driver import validate_config

config = yaml.safe_load(open("configs/ca_rules.yaml"))
errors = validate_config(config)
if errors:
    print("Validation errors:")
    for err in errors:
        print(f"  - {err}")
else:
    print("Config valid ✓")
```

## 11. Environment Setup

### 11.1 Python Environment

```bash
python --version  # 3.9+
pip install -r requirements.txt
pip install pytest  # For running tests
```

### 11.2 OpenROAD Integration

```bash
# Option 1: Use pre-installed OpenROAD
export OPENROAD_BIN=/path/to/openroad

# Option 2: Build from source
bash scripts/build_openroad_ifp.sh

# Option 3: Docker
docker-compose -f docker/docker-compose.yml up
```

### 11.3 Verify Setup

```bash
# Run quick tests
pytest tests/test_determinism.py -v

# Run one design end-to-end
python -m src.eval.experiment_driver \
  --mode full \
  --family synthetic \
  --seed 42
```

## 12. Known Issues and Workarounds

### Issue: Different results between runs
**Cause**: Global seed not fixed or environment randomness
**Fix**: Set seed explicitly in config and code

### Issue: OpenROAD binary not found
**Cause**: Not in PATH or path misconfigured
**Fix**: Use `--openroad /path/to/openroad` flag or set `OPENROAD_BIN` env var

### Issue: Benchmark files missing
**Cause**: IPSD/ISCAS collateral not downloaded
**Fix**: See ASAP7 PDK Setup section in main README; or use synthetic designs only

### Issue: Memory usage high
**Cause**: Large grid resolution (128+ cells) on many designs
**Fix**: Reduce `--family synthetic` or use smaller designs; or increase swap space

## 13. Performance Tuning

### 13.1 Speed Optimization

- **Smaller grid**: grid_resolution=32 reduces compute by ~4×
- **Fewer phases**: Reduce generation counts per phase
- **Disable expensive rules**: Skip boundary_regularization if not needed
- **Batch processing**: Use experiment driver with multiple designs

### 13.2 Quality Optimization

- **Larger grid**: grid_resolution=128 for finer placement granularity
- **More phases**: Increase generation counts for convergence
- **Higher weights**: Amplify important rules (connectivity for high-connectivity designs)
- **Different neighborhood**: Try "von_neumann" for different propagation patterns

### 13.3 Tradeoff Matrix

| Objective | Tune | Effect |
|-----------|------|--------|
| HPWL | ↑ beta, phases | Better wirelength |
| Density uniformity | ↑ alpha | More even utilization |
| Overlap-free | ↑ phases | More legalization iterations |
| Runtime | ↓ grid_resolution | 2-3× faster |
| Stability | ↓ alpha, beta | Smoother convergence |

## 14. References

- Main paper (citation in README)
- [FORMAL_CA_SPECIFICATION.md](FORMAL_CA_SPECIFICATION.md) — Detailed model description
- [configs/ca_rules.yaml](configs/ca_rules.yaml) — Full configuration template
- [src/ca/rule_library.py](src/ca/rule_library.py) — Rule implementation source code
