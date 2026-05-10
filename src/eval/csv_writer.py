"""CSV result writer for experiment metrics."""
from __future__ import annotations

import csv
import dataclasses
import logging
from pathlib import Path
from typing import Dict, List

from src.objectives.metrics import FloorplanMetrics

log = logging.getLogger(__name__)

COLUMNS = [
    "design", "method", "family",
    "area_um2", "core_area_um2", "aspect_ratio", "aspect_ratio_err",
    "overlap_count", "overlap_area_um2",
    "hpwl_um", "density_variance", "whitespace_frag",
    "outline_success", "runtime_s",
]


class CSVResultWriter:
    def __init__(self, output_dir: Path) -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def write_all(
        self,
        results: Dict[str, List[FloorplanMetrics]],
        filename: str = "results.csv",
        family_map: Dict[str, str] | None = None,
    ) -> Path:
        """Write all results (ablation levels × designs) to a single CSV."""
        rows = []
        for method, metrics_list in results.items():
            for m in metrics_list:
                row = dataclasses.asdict(m)
                row["method"] = method
                row["family"] = (family_map or {}).get(m.design, "unknown")
                rows.append({k: row.get(k, "") for k in COLUMNS})

        out_path = self.output_dir / filename
        with open(out_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=COLUMNS)
            writer.writeheader()
            writer.writerows(rows)

        log.info("Results written to %s (%d rows)", out_path, len(rows))
        return out_path

    def write_summary(self, results_path: Path) -> Path:
        """Write a summary CSV aggregated by method."""
        import pandas as pd
        df = pd.read_csv(results_path)
        summary = df.groupby("method").agg(
            designs      = ("design",         "count"),
            hpwl_mean    = ("hpwl_um",        "mean"),
            hpwl_std     = ("hpwl_um",        "std"),
            overlap_mean = ("overlap_count",   "mean"),
            frag_mean    = ("whitespace_frag", "mean"),
            runtime_mean = ("runtime_s",       "mean"),
        ).reset_index()
        out = results_path.parent / "summary.csv"
        summary.to_csv(out, index=False)
        log.info("Summary written to %s", out)
        return out
