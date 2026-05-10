"""
Generate the complete set of publication-ready figures for the repository README.

Produces:
  outputs/figures/
    floorplan_<design>_<method>.png   - macro placement snapshots
    heatmap_<design>_<phase>.png      - CA grid channel heatmaps
    convergence_<design>.png          - density convergence curves
    ablation_<metric>.png             - ablation bar charts
    compare_<metric>.png              - method comparison charts
    ca_rule_diagram.png               - rule interaction overview
    pipeline_overview.png             - framework pipeline diagram
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import math
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.gridspec as gridspec
from matplotlib.patches import FancyArrowPatch
from pathlib import Path
import yaml

from src.ca.grid_model import CAGrid, CH_DEN, CH_AFF, CH_NET, CH_BND, CH_OCC, CellState
from src.ca.evolution_scheduler import EvolutionScheduler
from src.data.registry import BenchmarkRegistry
from src.eval.baseline import BaselineFlow
from src.eval.ca_flow import CAFlow
from src.ifp_engine.openroad_wrapper import OpenROADRunner
from src.floorplan.macro_abstraction import FloorplanState, MacroRegion
from src.viz.publication_utils import pub_style, save_fig, COLORS

OUT = Path("outputs/figures")
OUT.mkdir(parents=True, exist_ok=True)

pub_style()

# ── palette ───────────────────────────────────────────────────────────────────
C = {
    "baseline":              "#6c757d",
    "density_only":          "#17a2b8",
    "density_connectivity":  "#fd7e14",
    "full_ca":               "#28a745",
}
METHODS = list(C.keys())
METHOD_LABELS = {
    "baseline":             "Baseline (ifp only)",
    "density_only":         "Density CA",
    "density_connectivity": "Density + Connectivity CA",
    "full_ca":              "Full CA (5 rules)",
}

# ══════════════════════════════════════════════════════════════════════════════
# 1.  PIPELINE OVERVIEW DIAGRAM
# ══════════════════════════════════════════════════════════════════════════════
def make_pipeline_overview():
    fig, ax = plt.subplots(figsize=(13, 3.4), facecolor="white")
    ax.set_facecolor("white")
    ax.axis("off")

    boxes = [
        ("Benchmark\nAdapter", "#dbeafe", "#1d4ed8"),
        ("CA Grid\nInit", "#dcfce7", "#15803d"),
        ("Phase 1–6\nCA Evolution", "#fef9c3", "#92400e"),
        ("Macro Region\nAssignment", "#fce7f3", "#9d174d"),
        ("Overlap\nRepair", "#f3e8ff", "#6b21a8"),
        ("OpenROAD\nifp Tcl", "#ffedd5", "#c2410c"),
        ("Metrics &\nFigures", "#f0fdf4", "#166534"),
    ]

    bw, bh, gap = 1.55, 0.9, 0.15
    total = len(boxes) * bw + (len(boxes) - 1) * gap
    x0 = (13 - total) / 2

    for i, (label, fc, ec) in enumerate(boxes):
        x = x0 + i * (bw + gap)
        rect = mpatches.FancyBboxPatch(
            (x, 1.0), bw, bh, boxstyle="round,pad=0.08",
            facecolor=fc, edgecolor=ec, linewidth=1.8, zorder=2
        )
        ax.add_patch(rect)
        ax.text(x + bw/2, 1.0 + bh/2, label,
                ha="center", va="center", fontsize=8.5, fontweight="bold",
                color=ec, zorder=3)
        if i < len(boxes) - 1:
            ax.annotate("", xy=(x + bw + gap, 1.45), xytext=(x + bw, 1.45),
                        arrowprops=dict(arrowstyle="->", color="#555", lw=1.5),
                        zorder=4)

    ax.set_xlim(0, 13); ax.set_ylim(0.5, 2.3)
    ax.set_title("CA-Floorplanner Pipeline", fontsize=12, fontweight="bold", pad=8)
    save_fig(fig, OUT / "pipeline_overview.png")
    print("  pipeline_overview.png")

# ══════════════════════════════════════════════════════════════════════════════
# 2.  CA RULE INTERACTION DIAGRAM
# ══════════════════════════════════════════════════════════════════════════════
def make_rule_diagram():
    fig, ax = plt.subplots(figsize=(10, 5), facecolor="white")
    ax.set_facecolor("white"); ax.axis("off")

    phases = ["Seed", "Compact", "Separate", "Cluster", "Legalize", "Smooth"]
    rules  = ["Density\nEqualiz.", "Connectivity\nAttraction", "Repulsion /\nSeparation",
              "Boundary\nRegular.", "Whitespace\nSmoothing"]
    active = [
        [1, 0, 0, 0, 1],   # seed
        [1, 1, 0, 0, 0],   # compact
        [0, 0, 1, 0, 0],   # separate
        [0, 1, 0, 0, 0],   # cluster
        [0, 0, 0, 1, 0],   # legalize
        [0, 0, 0, 0, 1],   # smooth
    ]
    rule_colors = ["#dbeafe","#dcfce7","#fce7f3","#fef9c3","#f3e8ff"]
    rule_ec     = ["#1d4ed8","#15803d","#9d174d","#92400e","#6b21a8"]

    nph, nru = len(phases), len(rules)
    cw, ch_, gx, gy = 1.7, 0.55, 0.12, 0.12
    ox, oy = 0.1, 0.5

    # rule headers
    for j, (rl, fc, ec) in enumerate(zip(rules, rule_colors, rule_ec)):
        x = ox + j * (cw + gx)
        rect = mpatches.FancyBboxPatch((x, oy + nph*(ch_+gy)), cw, 0.65,
                                        boxstyle="round,pad=0.05",
                                        facecolor=fc, edgecolor=ec, linewidth=1.5)
        ax.add_patch(rect)
        ax.text(x + cw/2, oy + nph*(ch_+gy) + 0.325, rl,
                ha="center", va="center", fontsize=7.5, color=ec, fontweight="bold")

    # phase rows
    for i, ph in enumerate(phases):
        y = oy + (nph - 1 - i) * (ch_ + gy)
        ax.text(ox - 0.08, y + ch_/2, ph, ha="right", va="center",
                fontsize=9, fontweight="bold", color="#333")
        for j, on in enumerate(active[i]):
            x = ox + j * (cw + gx)
            fc = rule_colors[j] if on else "#f8f9fa"
            ec = rule_ec[j]     if on else "#dee2e6"
            lw = 1.6 if on else 0.8
            rect = mpatches.FancyBboxPatch((x, y), cw, ch_,
                                            boxstyle="round,pad=0.04",
                                            facecolor=fc, edgecolor=ec, linewidth=lw)
            ax.add_patch(rect)
            if on:
                ax.text(x + cw/2, y + ch_/2, "✓", ha="center", va="center",
                        fontsize=13, color=ec, fontweight="bold")

    ax.set_xlim(-0.3, ox + nru*(cw+gx))
    ax.set_ylim(0, oy + nph*(ch_+gy) + 1.1)
    ax.set_title("Rule Activation per Evolution Phase", fontsize=12,
                 fontweight="bold", pad=8)
    save_fig(fig, OUT / "ca_rule_diagram.png")
    print("  ca_rule_diagram.png")

# ══════════════════════════════════════════════════════════════════════════════
# 3.  FLOORPLAN SNAPSHOTS  (all 3 designs × baseline + full_ca side by side)
# ══════════════════════════════════════════════════════════════════════════════
def make_floorplan_comparison(fps_baseline: dict, fps_ca: dict):
    designs = list(fps_baseline.keys())
    fig, axes = plt.subplots(2, len(designs),
                             figsize=(5.5 * len(designs), 10),
                             facecolor="white", constrained_layout=True)

    for col, name in enumerate(designs):
        for row, (fp, label) in enumerate([
            (fps_baseline[name], "Baseline (ifp only)"),
            (fps_ca[name],       "Full CA"),
        ]):
            ax = axes[row, col]
            ax.set_facecolor("#f8f9fa")
            core = fp.core_area
            cw = core[2] - core[0]; ch_ = core[3] - core[1]

            core_rect = mpatches.Rectangle((core[0], core[1]), cw, ch_,
                linewidth=1.5, edgecolor="#2ca02c", facecolor="#f0fdf4", zorder=1)
            ax.add_patch(core_rect)

            for m in fp.macros:
                color = COLORS[hash(m.name) % len(COLORS)]
                rect = mpatches.Rectangle((m.x, m.y), m.width, m.height,
                    linewidth=0.8, edgecolor="white",
                    facecolor=color, alpha=0.88, zorder=2)
                ax.add_patch(rect)
                if m.width > cw * 0.04:
                    ax.text(m.cx, m.cy, m.name, ha="center", va="center",
                            fontsize=5.5, color="white", fontweight="bold", zorder=3)

            ax.set_xlim(core[0] - cw*.04, core[2] + cw*.04)
            ax.set_ylim(core[1] - ch_*.04, core[3] + ch_*.04)
            ax.set_aspect("equal")
            ax.set_xlabel("X (µm)", fontsize=8)
            ax.set_ylabel("Y (µm)", fontsize=8)
            ax.tick_params(labelsize=7)
            ax.set_title(f"{name}\n{label}", fontsize=9, fontweight="bold")

    fig.suptitle("Floorplan Comparison: Baseline vs Full CA",
                 fontsize=13, fontweight="bold", y=1.01)
    save_fig(fig, OUT / "floorplan_comparison.png")
    print("  floorplan_comparison.png")


def make_single_floorplan(fp: FloorplanState, title: str, fname: str):
    fig, ax = plt.subplots(figsize=(5.5, 5.5), facecolor="white",
                           constrained_layout=True)
    ax.set_facecolor("#f8f9fa")
    core = fp.core_area
    cw = core[2] - core[0]; ch_ = core[3] - core[1]

    ax.add_patch(mpatches.Rectangle((core[0], core[1]), cw, ch_,
        linewidth=2, edgecolor="#2ca02c", facecolor="#f0fdf4", zorder=1))

    for m in fp.macros:
        color = COLORS[hash(m.name) % len(COLORS)]
        ax.add_patch(mpatches.Rectangle((m.x, m.y), m.width, m.height,
            linewidth=0.8, edgecolor="white", facecolor=color, alpha=0.88, zorder=2))
        if m.width > cw * 0.04:
            ax.text(m.cx, m.cy, m.name, ha="center", va="center",
                    fontsize=6, color="white", fontweight="bold", zorder=3)

    ax.set_xlim(core[0] - cw*.05, core[2] + cw*.05)
    ax.set_ylim(core[1] - ch_*.05, core[3] + ch_*.05)
    ax.set_aspect("equal")
    ax.set_xlabel("X (µm)"); ax.set_ylabel("Y (µm)")
    ax.tick_params(labelsize=8)
    ax.set_title(title, fontsize=11, fontweight="bold", pad=8)
    core_patch = mpatches.Patch(facecolor="#f0fdf4", edgecolor="#2ca02c",
                                 linewidth=2, label="Core area")
    ax.legend(handles=[core_patch], loc="upper right", fontsize=8)
    save_fig(fig, OUT / fname)
    print(f"  {fname}")

# ══════════════════════════════════════════════════════════════════════════════
# 4.  CA GRID HEATMAPS
# ══════════════════════════════════════════════════════════════════════════════
def make_heatmap(grid: CAGrid, title_prefix: str, fname: str):
    channels = [(CH_DEN, "Density",          "YlOrRd"),
                (CH_AFF, "Macro Affinity",   "Blues"),
                (CH_NET, "Net Pressure",     "Purples"),
                (CH_BND, "Boundary Press.",  "Greens")]
    fig, axes = plt.subplots(1, 4, figsize=(16, 4), facecolor="white",
                              constrained_layout=True)
    for ax, (ch, label, cmap) in zip(axes, channels):
        data = grid.state[:, :, ch]
        im = ax.imshow(data, origin="lower", cmap=cmap, vmin=0, vmax=1,
                       aspect="equal", interpolation="nearest")
        ax.set_title(label, fontsize=10, fontweight="bold")
        ax.set_xlabel("Column", fontsize=8); ax.set_ylabel("Row", fontsize=8)
        ax.tick_params(labelsize=7)
        cb = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
        cb.ax.tick_params(labelsize=7)

    fig.suptitle(f"{title_prefix} — CA Grid State", fontsize=12,
                 fontweight="bold")
    save_fig(fig, OUT / fname)
    print(f"  {fname}")

# ══════════════════════════════════════════════════════════════════════════════
# 5.  CONVERGENCE CURVES
# ══════════════════════════════════════════════════════════════════════════════
def make_convergence(histories: dict, fname: str):
    """histories = {label: [float,...]}"""
    fig, ax = plt.subplots(figsize=(7, 3.8), facecolor="white",
                            constrained_layout=True)
    for i, (label, hist) in enumerate(histories.items()):
        ax.plot(hist, label=label, color=COLORS[i % len(COLORS)],
                linewidth=1.8, alpha=0.9)
    ax.set_xlabel("Generation", fontsize=10)
    ax.set_ylabel("Mean Grid Density", fontsize=10)
    ax.set_title("CA Evolution — Density Convergence", fontsize=12,
                 fontweight="bold")
    ax.set_ylim(0, 1)
    ax.legend(loc="upper right", fontsize=8, framealpha=0.9)
    save_fig(fig, OUT / fname)
    print(f"  {fname}")

# ══════════════════════════════════════════════════════════════════════════════
# 6.  ABLATION BAR CHARTS  (rewritten for higher quality)
# ══════════════════════════════════════════════════════════════════════════════
ABLATION_DATA = {
    # (design, method) → metrics
    ("synth_small",  "baseline"):             dict(hpwl=1520.0,  overlaps=0,  frag=0.652, dvar=0.108, rt=0.001),
    ("synth_small",  "density_only"):         dict(hpwl=1520.0,  overlaps=0,  frag=0.644, dvar=0.130, rt=0.019),
    ("synth_small",  "density_connectivity"): dict(hpwl=629.8,   overlaps=1,  frag=0.551, dvar=0.104, rt=0.030),
    ("synth_small",  "full_ca"):              dict(hpwl=656.0,   overlaps=0,  frag=0.529, dvar=0.124, rt=0.065),
    ("synth_medium", "baseline"):             dict(hpwl=6460.0,  overlaps=0,  frag=0.774, dvar=0.098, rt=0.001),
    ("synth_medium", "density_only"):         dict(hpwl=6549.1,  overlaps=0,  frag=0.759, dvar=0.108, rt=0.023),
    ("synth_medium", "density_connectivity"): dict(hpwl=2216.6,  overlaps=10, frag=0.536, dvar=0.061, rt=0.038),
    ("synth_medium", "full_ca"):              dict(hpwl=2086.0,  overlaps=10, frag=0.537, dvar=0.060, rt=0.128),
    ("synth_large",  "baseline"):             dict(hpwl=33250.0, overlaps=0,  frag=0.833, dvar=0.077, rt=0.001),
    ("synth_large",  "density_only"):         dict(hpwl=33250.0, overlaps=0,  frag=0.826, dvar=0.108, rt=0.033),
    ("synth_large",  "density_connectivity"): dict(hpwl=6843.7,  overlaps=66, frag=0.530, dvar=0.042, rt=0.074),
    ("synth_large",  "full_ca"):              dict(hpwl=11112.8, overlaps=45, frag=0.518, dvar=0.052, rt=0.101),
}
DESIGNS = ["synth_small", "synth_medium", "synth_large"]

def make_ablation_grouped(metric_key: str, ylabel: str, title: str, fname: str,
                           pct_label: bool = False):
    x     = np.arange(len(DESIGNS))
    width = 0.19
    fig, ax = plt.subplots(figsize=(9, 4.5), facecolor="white",
                            constrained_layout=True)

    for i, method in enumerate(METHODS):
        vals = [ABLATION_DATA[(d, method)][metric_key] for d in DESIGNS]
        offset = (i - 1.5) * width
        bars = ax.bar(x + offset, vals, width, label=METHOD_LABELS[method],
                      color=C[method], edgecolor="white", linewidth=0.6,
                      alpha=0.92, zorder=3)
        # value labels on bars
        for bar, v in zip(bars, vals):
            if v > 0:
                ax.text(bar.get_x() + bar.get_width()/2,
                        bar.get_height() + max(vals)*0.01,
                        f"{v:.0f}" if v >= 10 else f"{v:.2f}",
                        ha="center", va="bottom", fontsize=6.5, color="#333")

    ax.set_xticks(x)
    ax.set_xticklabels(["Small\n(4 macros)", "Medium\n(8 macros)", "Large\n(16 macros)"],
                       fontsize=10)
    ax.set_ylabel(ylabel, fontsize=10)
    ax.set_title(title, fontsize=12, fontweight="bold", pad=8)
    ax.legend(loc="upper left", fontsize=8.5, framealpha=0.92,
              bbox_to_anchor=(0.0, 1.0))
    ax.grid(axis="y", linestyle="--", alpha=0.4, zorder=0)
    ax.set_axisbelow(True)
    save_fig(fig, OUT / fname)
    print(f"  {fname}")


def make_improvement_chart():
    """Horizontal bar chart: % HPWL improvement of full_ca over baseline."""
    improvements = []
    for d in DESIGNS:
        base = ABLATION_DATA[(d, "baseline")]["hpwl"]
        ca   = ABLATION_DATA[(d, "full_ca")]["hpwl"]
        improvements.append((d, (base - ca) / base * 100))

    fig, ax = plt.subplots(figsize=(7, 3.2), facecolor="white",
                            constrained_layout=True)
    names = [d.replace("synth_", "").capitalize() for _, d2 in [("",d) for d in DESIGNS] for d in [d2]]
    names = [d.replace("synth_","").capitalize() for d in DESIGNS]
    vals  = [imp for _, imp in improvements]

    bars = ax.barh(names, vals, color=[C["full_ca"]]*3, edgecolor="white",
                   alpha=0.9, height=0.5)
    for bar, v in zip(bars, vals):
        ax.text(v + 0.5, bar.get_y() + bar.get_height()/2,
                f"{v:.1f}%", va="center", fontsize=10, fontweight="bold",
                color=C["full_ca"])

    ax.set_xlabel("HPWL Improvement over Baseline (%)", fontsize=10)
    ax.set_title("Full CA vs Baseline — HPWL Reduction", fontsize=12,
                 fontweight="bold", pad=8)
    ax.set_xlim(0, max(vals) * 1.25)
    ax.axvline(0, color="#333", linewidth=0.8)
    ax.grid(axis="x", linestyle="--", alpha=0.4)
    ax.set_axisbelow(True)
    save_fig(fig, OUT / "improvement_hpwl.png")
    print("  improvement_hpwl.png")


def make_radar_chart():
    """Radar chart comparing 4 ablation methods across 5 normalised metrics."""
    import matplotlib.patches as mp

    labels   = ["HPWL\n(lower)", "Overlap\n(lower)", "Density Var\n(lower)",
                 "WS Frag\n(lower)", "Runtime\n(lower)"]
    n = len(labels)

    # Normalise each metric to [0,1] where 1 = best (min normalised for lower-is-better)
    def norm(key, vals):
        lo, hi = min(vals), max(vals)
        if hi == lo: return [1.0]*len(vals)
        return [1 - (v - lo)/(hi - lo) for v in vals]   # 1=best (lowest raw)

    method_data = {}
    for method in METHODS:
        hpwl = [ABLATION_DATA[(d,method)]["hpwl"]     for d in DESIGNS]
        ovlp = [ABLATION_DATA[(d,method)]["overlaps"] for d in DESIGNS]
        dvar = [ABLATION_DATA[(d,method)]["dvar"]     for d in DESIGNS]
        frag = [ABLATION_DATA[(d,method)]["frag"]     for d in DESIGNS]
        rt   = [ABLATION_DATA[(d,method)]["rt"]       for d in DESIGNS]
        method_data[method] = [np.mean(v) for v in [hpwl, ovlp, dvar, frag, rt]]

    all_vals = {i: [method_data[m][i] for m in METHODS] for i in range(n)}
    normed   = {m: [1-(method_data[m][i]-min(all_vals[i]))/(max(all_vals[i])-min(all_vals[i])+1e-9)
                    for i in range(n)] for m in METHODS}

    angles = np.linspace(0, 2*np.pi, n, endpoint=False).tolist()
    angles += angles[:1]

    fig, ax = plt.subplots(1, 1, figsize=(6, 6), subplot_kw=dict(polar=True),
                           facecolor="white", constrained_layout=True)
    ax.set_facecolor("white")

    for method in METHODS:
        vals = normed[method] + normed[method][:1]
        ax.plot(angles, vals, color=C[method], linewidth=2.2, label=METHOD_LABELS[method])
        ax.fill(angles, vals, color=C[method], alpha=0.12)

    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(labels, fontsize=9)
    ax.set_ylim(0, 1)
    ax.set_yticks([0.25, 0.5, 0.75, 1.0])
    ax.set_yticklabels(["0.25","0.50","0.75","1.0"], fontsize=7, color="#666")
    ax.yaxis.set_tick_params(labelsize=7)
    ax.set_title("Multi-Metric Comparison\n(1.0 = best per axis)", fontsize=11,
                 fontweight="bold", pad=20)
    ax.legend(loc="upper right", bbox_to_anchor=(1.4, 1.15), fontsize=8.5,
              framealpha=0.9)
    save_fig(fig, OUT / "radar_comparison.png")
    print("  radar_comparison.png")


# ══════════════════════════════════════════════════════════════════════════════
# 7.  PHASE TIMELINE (gantt-style)
# ══════════════════════════════════════════════════════════════════════════════
def make_phase_gantt():
    phases = ["Seed", "Compact", "Separate", "Cluster", "Legalize", "Smooth"]
    gens   = [20, 40, 30, 30, 20, 20]  # max generations per phase (from config)
    colors = ["#dbeafe","#dcfce7","#fce7f3","#fff7cd","#f3e8ff","#ffddd2"]
    edges  = ["#1d4ed8","#15803d","#9d174d","#92400e","#6b21a8","#c2410c"]

    fig, ax = plt.subplots(figsize=(10, 2.6), facecolor="white",
                           constrained_layout=True)
    ax.set_facecolor("white")

    x = 0
    for phase, g, fc, ec in zip(phases, gens, colors, edges):
        rect = mpatches.FancyBboxPatch((x, 0.15), g, 0.7,
            boxstyle="round,pad=0.8", facecolor=fc, edgecolor=ec, linewidth=1.8)
        ax.add_patch(rect)
        ax.text(x + g/2, 0.5, f"{phase}\n({g} gen)",
                ha="center", va="center", fontsize=9, color=ec, fontweight="bold")
        x += g

    ax.set_xlim(-2, sum(gens) + 2)
    ax.set_ylim(0, 1)
    ax.axis("off")
    ax.set_title("CA Evolution Phase Schedule  (total: 160 max generations)",
                 fontsize=11, fontweight="bold", pad=6)
    save_fig(fig, OUT / "phase_timeline.png")
    print("  phase_timeline.png")


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════
def main():
    print("Generating figures...")

    # ── static diagrams ───────────────────────────────────────────────────────
    make_pipeline_overview()
    make_rule_diagram()
    make_phase_gantt()

    # ── run CA flow on all 3 synthetic designs ────────────────────────────────
    with open("configs/benchmarks.yaml") as f:
        bench_cfg = yaml.safe_load(f)
    with open("configs/ca_rules.yaml") as f:
        ca_cfg = yaml.safe_load(f)

    global_cfg  = ca_cfg["global"]
    rule_sets   = ca_cfg["rule_sets"]
    rule_params = ca_cfg["rule_params"]

    registry = BenchmarkRegistry("configs/benchmarks.yaml")
    designs  = [d for d in registry.ready() if d.family == "synthetic"]

    runner = OpenROADRunner(log_dir=Path("outputs/logs"))

    fps_baseline: dict = {}
    fps_ca:       dict = {}
    conv_histories: dict = {}

    for design in designs:
        print(f"\n  Running flows for {design.name}...")

        # baseline
        base_flow = BaselineFlow(runner, Path("outputs"))
        fp_base, _ = base_flow.run(design)
        fps_baseline[design.name] = fp_base
        make_single_floorplan(fp_base,
            f"{design.name} — Baseline (ifp only)",
            f"floorplan_{design.name}_baseline.png")

        # full_ca
        ca_flow = CAFlow(
            runner       = runner,
            output_dir   = Path("outputs"),
            rule_set_cfg = rule_sets["full_ca"],
            rule_params  = rule_params,
            grid_rows    = global_cfg.get("grid_resolution", 64),
            grid_cols    = global_cfg.get("grid_resolution", 64),
            neighborhood = global_cfg.get("neighborhood", "moore"),
            convergence_eps = float(global_cfg.get("convergence_eps", 1e-5)),
            seed         = global_cfg.get("seed", 42),
        )
        fp_ca, _, evo_record = ca_flow.run(design, rule_set_name="full_ca")
        fps_ca[design.name] = fp_ca
        make_single_floorplan(fp_ca,
            f"{design.name} — Full CA (5 rules, 6 phases)",
            f"floorplan_{design.name}_full_ca.png")

        # Heatmap of evolved grid (rebuild for viz)
        core = fp_ca.core_area
        grid = CAGrid(rows=global_cfg.get("grid_resolution", 64),
                      cols=global_cfg.get("grid_resolution", 64),
                      core_area=core, seed=global_cfg.get("seed", 42))
        for m in design.macros:
            r, c = grid.phy_to_grid(m.x + m.width/2, m.y + m.height/2)
            grid.place_macro(r - 1, c - 1,
                             max(1, int(m.width/grid.cell_w)),
                             max(1, int(m.height/grid.cell_h)))
        grid.seed_density(design.num_stdcells * 0.19 * 1.4, 0.5)
        make_heatmap(grid, design.name, f"heatmap_{design.name}_initial.png")

        # Convergence
        if evo_record and evo_record.density_history:
            conv_histories[design.name] = evo_record.density_history

    # Comparison floorplan (3 designs × 2 methods)
    make_floorplan_comparison(fps_baseline, fps_ca)

    # Convergence curves
    if conv_histories:
        make_convergence(conv_histories, "convergence_density.png")

    # ── ablation charts ───────────────────────────────────────────────────────
    make_ablation_grouped("hpwl",     "HPWL (µm)",          "Ablation — HPWL",                  "ablation_hpwl_um.png")
    make_ablation_grouped("overlaps", "Macro Overlap Count", "Ablation — Overlap Count",          "ablation_overlap_count.png")
    make_ablation_grouped("frag",     "Whitespace Frag.",    "Ablation — Whitespace Fragmentation","ablation_whitespace_frag.png")
    make_ablation_grouped("dvar",     "Density Variance",    "Ablation — Density Variance",       "ablation_density_variance.png")
    make_ablation_grouped("rt",       "Runtime (s)",         "Ablation — Runtime",                "ablation_runtime_s.png")
    make_improvement_chart()
    make_radar_chart()
    make_phase_gantt()

    print(f"\nAll figures saved to {OUT}/")
    print("Files:")
    for f in sorted(OUT.glob("*.png")):
        kb = f.stat().st_size // 1024
        print(f"  {f.name:50s} {kb:>5} KB")


if __name__ == "__main__":
    main()
