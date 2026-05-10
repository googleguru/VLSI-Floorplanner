"""Markdown table and section generator for README auto-update."""
from __future__ import annotations

from pathlib import Path
from typing import List, Optional

import pandas as pd


def results_table_md(csv_path: Path, top_n: int = 20) -> str:
    """Generate a markdown table from a results CSV."""
    try:
        df = pd.read_csv(csv_path)
    except Exception:
        return "_Results not yet available._\n"

    cols = [c for c in [
        "design", "method",
        "hpwl_um", "overlap_count", "density_variance",
        "whitespace_frag", "outline_success", "runtime_s",
    ] if c in df.columns]

    df = df[cols].head(top_n)

    # Format floats
    for col in ["hpwl_um", "density_variance", "whitespace_frag",
                 "outline_success", "runtime_s"]:
        if col in df.columns:
            df[col] = df[col].apply(lambda v: f"{v:.3f}" if pd.notna(v) else "—")

    lines = []
    header = "| " + " | ".join(cols) + " |"
    sep    = "| " + " | ".join("---" for _ in cols) + " |"
    lines.append(header)
    lines.append(sep)
    for _, row in df.iterrows():
        lines.append("| " + " | ".join(str(row[c]) for c in cols) + " |")
    return "\n".join(lines) + "\n"


def summary_table_md(summary_csv: Path) -> str:
    try:
        df = pd.read_csv(summary_csv)
    except Exception:
        return "_Summary not yet available._\n"

    cols = [c for c in [
        "method", "designs", "hpwl_mean", "hpwl_std",
        "overlap_mean", "frag_mean", "runtime_mean",
    ] if c in df.columns]

    df = df[cols]
    for col in ["hpwl_mean", "hpwl_std", "overlap_mean", "frag_mean", "runtime_mean"]:
        if col in df.columns:
            df[col] = df[col].apply(lambda v: f"{v:.3f}" if pd.notna(v) else "—")

    lines = []
    header = "| " + " | ".join(cols) + " |"
    sep    = "| " + " | ".join("---" for _ in cols) + " |"
    lines.append(header)
    lines.append(sep)
    for _, row in df.iterrows():
        lines.append("| " + " | ".join(str(row[c]) for c in cols) + " |")
    return "\n".join(lines) + "\n"


def figure_embed_md(figures_dir: Path, pattern: str = "*.png") -> str:
    figs = sorted(figures_dir.glob(pattern))
    if not figs:
        return "_No figures generated yet._\n"
    lines = []
    for f in figs[:12]:   # cap at 12 to keep README manageable
        lines.append(f"![{f.stem}]({f.relative_to(Path('.'))})")
    return "\n".join(lines) + "\n"
