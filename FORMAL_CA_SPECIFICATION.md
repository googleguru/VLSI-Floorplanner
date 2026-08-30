# Cellular Automata Floorplanning Model - Formal Specification

## 1. CA Grid Representation

### 1.1 Grid Structure
The core area is discretized into a uniform **2D grid of R × C cells** (typically 64 × 64), where:
- **R** = number of rows (y-axis)
- **C** = number of columns (x-axis)
- Each cell (r, c) contains a **6-channel state vector** S(r,c) ∈ ℝ^6

### 1.2 State Channels
Each cell's state is represented as a 6-tuple:
```
S(r,c) = [occupancy, density, macro_affinity, boundary_pressure, net_pressure, blockage]
          [CH_OCC,   CH_DEN,  CH_AFF,        CH_BND,            CH_NET,      CH_BLK]
```

#### Channel 0: Occupancy (CH_OCC) - Discrete
- Domain: {0, 1, 2, 3} (enumerated discrete states)
- **0 = EMPTY**: Standard-cell region, available for stdcell placement
- **1 = BLOCKAGE**: Hard keepout region, unavailable
- **2 = MACRO**: Macro cell region, already placed/seeded
- **3 = STDCELL**: Explicitly marked standard-cell region

#### Channel 1: Density (CH_DEN) - Continuous
- Domain: [0, 1]
- Semantics: **Utilization estimate** for the cell
  - 0 = completely empty
  - 1 = fully occupied
- Used for macro placement attraction and whitespace control
- Rule 235 operates primarily on this channel to eliminate isolated islands

#### Channel 2: Macro Affinity (CH_AFF) - Continuous
- Domain: [0, 1]
- Semantics: **Attraction strength** toward macro-bearing placement zones
  - 0 = repulsive (avoid macros here)
  - 1 = highly attractive (place macros here)
- Updated by **connectivity_attraction** rule to concentrate macros around net hubs
- Combined with density to form zone score for macro assignment

#### Channel 3: Boundary Pressure (CH_BND) - Continuous
- Domain: [0, 1]
- Semantics: **Inverse distance to die edge** (higher at edges)
  - 1.0 = at die boundary
  - 0.0 = at core center
- Initialized based on geometric distance; immutable during evolution
- Used by **boundary_regularization** rule to push content toward center

#### Channel 4: Net Pressure (CH_NET) - Continuous
- Domain: [0, 1]
- Semantics: **Accumulated net connectivity load** (input from netlist)
  - Reflects total estimated routing demand passing through cell
  - Set externally from benchmark netlists
  - Immutable during evolution (unless explicitly reset)
- Used by **connectivity_attraction** rule to position macros near high-demand regions

#### Channel 5: Blockage (CH_BLK) - Discrete
- Domain: {0, 1}
- Semantics: **Hard keepout flag**
  - 0 = normal cell
  - 1 = permanent blockage (cannot be modified)
- Prevents all rules from modifying cells in blockage regions


## 2. Coordinate System

### 2.1 Grid Coordinates
- **Grid space**: (row, col) where row ∈ [0, R-1], col ∈ [0, C-1]
- **Row indexing**: row=0 at bottom (y=llx), row=R-1 at top (y=ury)
- **Col indexing**: col=0 at left (x=llx), col=C-1 at right (x=urx)

### 2.2 Physical Coordinates
- **Physical space**: (x, y) in micrometers (µm)
- **Core area**: (llx, lly, urx, ury) in µm
- **Cell size**: 
  - cell_w = (urx - llx) / C
  - cell_h = (ury - lly) / R
- **Conversion**:
  ```
  (x, y) → (row, col) = ((y - lly) / cell_h, (x - llx) / cell_w)  [floored, clamped]
  (row, col) → (x, y) = (llx + (col + 0.5) * cell_w, lly + (row + 0.5) * cell_h)
  ```


## 3. Neighborhood Definition

### 3.1 Moore Neighborhood
The **Moore neighborhood** of cell (r,c) includes all 8 adjacent cells:
```
N_M(r,c) = {(r±1, c±1), (r±1, c), (r, c±1)}
           excluding out-of-bounds cells
```
Total neighbors: 3–8 depending on proximity to boundaries.

Boundary handling: **Zero-padding** (neighbors outside grid assumed to have value 0).

### 3.2 Von Neumann Neighborhood
The **Von Neumann neighborhood** includes 4 orthogonal neighbors:
```
N_VN(r,c) = {(r±1, c), (r, c±1)}
           excluding out-of-bounds
```
Total neighbors: 2–4 depending on position.

### 3.3 Totalistic Neighborhood Operators
Rules operate on **totalistic** neighborhood functions (sum or mean of values across neighbors):

- **channel_sum_moore(state, ch)**: Sum values in channel ch across 8 neighbors
- **channel_mean_moore(state, ch)**: Mean value in channel ch across 8 neighbors
- Similar variants for Von Neumann

Result shape: (R, C), one value per cell representing neighborhood aggregate.


## 4. CA Evolution Mechanism

### 4.1 Synchronous Update
The CA evolves in **discrete generations**:
1. **Read phase**: Compute new state for all cells based on current state
2. **Apply phase**: Simultaneously update all cells
3. **Clamp phase**: Enforce constraints and boundary conditions

### 4.2 Update Rule Composition
Each generation applies a weighted combination of rule families:
```
Δstate(r,c) = Σ_i w_i × rule_i(state, params, neighborhood)
```

Where:
- w_i ∈ ℝ (weight for rule i, typically ~1.0)
- rule_i: (ℝ^(R×C×6), dict, str) → ℝ^(R×C×6)
- Each rule returns a delta (change tensor), added to state

### 4.3 Constraint Enforcement
After all rules apply:
```
state_new = state_old + Δstate
```

Clamps applied:
1. **Continuous channels** (1–4): clip to [0, 1]
2. **Occupancy (0)**: preserve MACRO and BLOCKAGE states (do not overwrite)
3. **Blockage (5)**: immutable (reset to original post-clamp if modified)

### 4.4 Deterministic Tie-Breaking
When multiple cells compete for the same "resource" (e.g., density redistribution), ties are broken **spatially**: prefer lower row indices, then lower column indices. This ensures repeatability given identical initial state and parameters.


## 5. Rule Families (6 Rules)

### 5.1 Density Equalization (Rule 1)
**Goal**: Redistribute utilization mass from high-density to low-density regions.

**Formula**:
```
Δ_den[r,c] = α × (mean_neighbor_den[r,c] - den[r,c])  if |diff| > threshold
            = 0                                          otherwise

where α ∈ [0, 1] (default 0.25)
      threshold ∈ [0, 1] (default 0.05)
```

**Domain**: Applied to free cells (not blockage, not macro).

### 5.2 Connectivity Attraction (Rule 2)
**Goal**: Concentrate macros near high-connectivity (net-pressure) regions.

**Formula**:
```
Δ_aff[r,c] = β × net_pressure[r,c] × (1 - aff[r,c])
Δ_den[r,c] += 0.1 × net_pressure[r,c]  (weaker density nudge)

where β ∈ [0, 1] (default 0.30)
      net_pressure clipped to [0, 1]
```

**Semantics**: High net-pressure cells become more attractive for macros; density spreads toward these hubs.

### 5.3 Repulsion/Separation (Rule 3)
**Goal**: Push macro-bearing cells apart to avoid overlap.

**Formula**:
```
Δ_aff[r,c] = -γ × overlap_pressure[r,c]

where overlap_pressure = # of immediate neighbors with aff > 0.5
      γ ∈ [0, 1] (default 0.40)
```

**Semantics**: If surrounded by other macros, affinity decreases, pushing cells away.

### 5.4 Boundary Regularization (Rule 4)
**Goal**: Push content away from die boundaries toward the core.

**Formula**:
```
Δ_den[r,c] = -λ_b × boundary_pressure[r,c] × den[r,c]

where λ_b ∈ [0, 1] (default 0.35)
```

**Semantics**: Boundary cells lose density; it redistributes inward (conservative update).

### 5.5 Whitespace Smoothing (Rule 5)
**Goal**: Apply Gaussian smoothing to density for uniform utilization.

**Formula**:
```
Δ_den[r,c] = σ × (gaussian_smooth(den)[r,c] - den[r,c])

where σ ∈ [0, 1] (default 0.6)
      gaussian_smooth applies kernel with std=1.5 cells
```

**Semantics**: Blends density toward neighborhood averages; promotes connectivity.

### 5.6 Rule 235 (Wolfram Rule 235 Generalized)
**Goal**: Eliminate isolated density islands; preserve intentional whitespace.

**Wolfram Rule 235 (binary: 11101011)** encodes:
```
Pattern 111 → 1    Pattern 110 → 1    Pattern 101 → 1    Pattern 100 → 0
Pattern 011 → 1    Pattern 010 → 0    Pattern 001 → 1    Pattern 000 → 1
```

**2D Generalization** (totalistic, Moore):
```
1. Binary active map: active[r,c] = (den[r,c] ≥ threshold)

2. Neighbor count: nbr_cnt[r,c] = Σ active[neighbor] (0–8)

3. Cell state transitions:
   - Isolated (active=1, nbr_cnt < 1)     → die         [maps 010→0]
   - Dead with live neighbors (active=0, nbr_cnt ≥ 1) → birth  [maps 001→1]
   - Void (active=0, nbr_cnt=0)           → stay void   [maps 000→1]
   - Connected (active=1, nbr_cnt ≥ 1)   → survive      [maps 011,111→1]

4. Target density update:
   target[r,c] = 0           if isolated
               = threshold   if birth
               = den[r,c]    otherwise

5. Density step:
   Δ_den[r,c] = strength × (target[r,c] - den[r,c])

where threshold ∈ [0, 1] (default 0.30)
      strength ∈ [0, 1] (default 0.20)
      birth_neighbors (default 1)
      survival_neighbors (default 1)
```

**Semantics**: Cleans up fragmented/scattered density; creates coherent macro zones for placer.


## 6. Evolution Phases

The CA evolution is divided into **named phases**, each specifying:
- Which rules to activate
- Number of generations to run
- Weights for rule contributions

### 6.1 Typical Phase Ordering (Full CA)
1. **Seed** (20 gen): density_equalization
   - Spread density evenly across free space
   
2. **Compact** (40 gen): density_equalization + connectivity_attraction
   - Cluster density around high-connectivity regions
   
3. **Separate** (30 gen): repulsion_separation
   - Push macro clusters apart to reduce overlap risk
   
4. **Cluster** (30 gen): connectivity_attraction
   - Re-attract clusters toward net hubs
   
5. **Rule235_Cleanup** (25 gen): rule_235
   - Eliminate isolated islands; sharpen zone boundaries
   
6. **Legalize** (20 gen): boundary_regularization
   - Push all content toward core center
   
7. **Smooth** (20 gen): whitespace_smoothing
   - Final smoothing for placement algorithm

### 6.2 Early Stopping
A phase terminates early if:
```
max(|Δstate[r,c]| for all r,c) < convergence_eps
```
Default: convergence_eps = 1e-5.

This prevents wasteful iterations once a phase has stabilized.


## 7. Discrete Floorplan Extraction

### 7.1 Macro Assignment
After CA evolution, continuous density field → discrete macro placements:

1. **Zone scoring**: For each cell (r,c):
   ```
   score[r,c] = 0.65 × aff[r,c] + 0.35 × (den[r,c] ≥ 0.30)
   ```

2. **Region detection**: Connected components on score field (threshold ~0.4)

3. **Macro placement**: For each macro in design:
   - Find highest-score region that fits
   - Place center at region's centroid
   - Clamp to core boundaries

### 7.2 Overlap Repair
Post-placement, resolve remaining overlaps:
1. **Greedy push-apart**: Sort macros by area; resolve overlaps pairwise
2. **Min-displacement**: Iteratively optimize positions for minimal movement
3. **Tetris legalization** (if still overlaps): Place sequentially into free space

### 7.3 Outline Legalization
Clip any out-of-bounds macros back into core:
```
x_new = max(llx, min(urx - width, x_old))
y_new = max(lly, min(ury - height, y_old))
```


## 8. Hybrid CA vs. Pure CA

### 8.1 Why "Hybrid"?
The method is a **generalized, hybrid cellular automaton** rather than a "pure" CA:

1. **Continuous state** (not binary): Channels are ℝ-valued, not {0,1}
2. **External state** (net_pressure): Input from netlist, not purely self-generated
3. **Non-local operations**: Gaussian smoothing, connected-component labeling transcend local neighborhoods
4. **Non-deterministic seeding** (though seeded for reproducibility)

### 8.2 CA Inspiration
The method preserves CA principles:
- **Discrete grid**: Spatial discretization
- **Local neighborhoods**: Most rules operate on Moore/VN neighborhoods
- **Synchronous updates**: All cells updated simultaneously
- **Parallel rule composition**: Multiple rules applied in parallel per generation
- **Iterated refinement**: Repeated application for emergent macro placement


## 9. Parameters and Configuration

### 9.1 Global Parameters (ca_rules.yaml → global)
```yaml
global:
  seed: 42                           # RNG seed for reproducibility
  grid_resolution: 64                # R=C (square grid)
  neighborhood: "moore"              # or "von_neumann"
  max_generations: 200               # hard limit per phase
  convergence_eps: 1e-5              # early stop threshold
```

### 9.2 Rule-Specific Parameters (ca_rules.yaml → rule_params)

#### density_equalization
- `alpha`: Fraction of excess density to redistribute (default 0.25)
- `threshold`: Minimum density difference to trigger (default 0.05)

#### connectivity_attraction
- `beta`: Attraction strength (default 0.30)
- `max_net_pressure`: Clamp for net pressure (default 1.0)

#### repulsion_separation
- `gamma`: Repulsion strength (default 0.40)

#### boundary_regularization
- `lambda_b`: Boundary push strength (default 0.35)

#### whitespace_smoothing
- `sigma`: Gaussian smoothing std (default 0.6)
- `target_utilization`: Target density level (default 0.70)

#### rule_235
- `threshold`: Density threshold for "active" (default 0.30)
- `strength`: Rate of convergence (default 0.20)
- `birth_neighbors`: Min neighbors to trigger birth (default 1)
- `survival_neighbors`: Min neighbors to survive (default 1)

### 9.3 Rule Phases (ca_rules.yaml → rule_sets → {full_ca, ...})
Each rule set defines:
```yaml
phases:
  - name: phase_name
    rules: [rule1, rule2, ...]
    generations: N
weights:
  rule1: w1
  rule2: w2
```


## 10. Determinism and Reproducibility

### 10.1 Deterministic Execution
Given:
- Same seed (for RNG initialization)
- Same grid resolution and core area
- Same rule configuration and parameters
- Same input macros and netlists

The CA evolution produces **bitwise identical** results (modulo floating-point precision).

### 10.2 Randomness Sources
1. **Grid initialization** (seed_density): Controlled by global seed
2. **Macro placement** (MacroAssigner): Deterministic given grid
3. **Tie-breaking** (deterministic_tiebreak): Spatial ordering, no randomness

### 10.3 Reproducibility Guarantees
- Same seed → same macro placement
- Same configuration → same convergence trajectory
- Multi-run average metrics are identical (no averaging noise)


## 11. Computational Complexity

- **Grid state**: O(R × C × 6) = O(4096) for 64×64 grid
- **Per-generation cost**: O(R × C × neighborhood_size) per rule ≈ O(n) to O(n²) depending on operation
- **Total evolution**: 150–200 generations typical, ~O(1–5ms) per full run (CPU)
- **Overlap repair**: O(M²) where M = # macros (~16–32 typical)
- **Rule 235**: O(R × C) for island detection via connected-component labeling


## References

- Wolfram, Stephen. "A New Kind of Science." Wolfram Media, 2002.
- Elementary CA Rule 235: https://mathworld.wolfram.com/ElementaryCellularAutomaton.html
- Moore, Edward F. "Machine Models of Self-Reproduction." PNAS, 1962.
- Von Neumann, John. "Self-Reproducing Automata." University of Illinois Press, 1966.
