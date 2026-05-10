"""Main experiment driver CLI.

Usage:
  python -m src.eval.experiment_driver --mode baseline --config configs/benchmarks.yaml
  python -m src.eval.experiment_driver --mode full     --ca-config configs/ca_rules.yaml
  python -m src.eval.experiment_driver --mode ablation
  python -m src.eval.experiment_driver --mode rule-search
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Optional

import click
import yaml

from src.data.registry import BenchmarkRegistry
from src.eval.baseline import BaselineFlow
from src.eval.ca_flow import CAFlow
from src.eval.ablation import AblationStudy
from src.eval.rule_search import RuleSearcher
from src.eval.csv_writer import CSVResultWriter
from src.ifp_engine.openroad_wrapper import OpenROADRunner
from src.viz.comparison_charts import ComparisonChartPlotter
from src.viz.floorplan_renderer import FloorplanRenderer
from src.viz.heatmap import HeatmapPlotter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


@click.command()
@click.option("--mode", required=True,
              type=click.Choice(["baseline", "full", "ablation", "rule-search"]),
              help="Experiment mode.")
@click.option("--config",    default="configs/benchmarks.yaml",
              help="Benchmark config path.")
@click.option("--ca-config", default="configs/ca_rules.yaml",
              help="CA rule config path.")
@click.option("--output",    default="outputs",
              help="Output directory root.")
@click.option("--family",    default=None,
              help="Only run designs from this benchmark family.")
@click.option("--openroad",  default=None,
              help="Path to openroad binary (auto-detected if omitted).")
@click.option("--seed",      default=42, type=int,
              help="Global random seed.")
def cli(
    mode:      str,
    config:    str,
    ca_config: str,
    output:    str,
    family:    Optional[str],
    openroad:  Optional[str],
    seed:      int,
) -> None:
    """CA-Floorplanner experiment driver."""
    output_dir = Path(output)
    output_dir.mkdir(parents=True, exist_ok=True)
    for sub in ("tcl", "floorplans", "figures", "tables", "logs", "reports"):
        (output_dir / sub).mkdir(exist_ok=True)

    # Load benchmark registry
    registry = BenchmarkRegistry(config)
    designs  = registry.ready()
    if family:
        designs = [d for d in designs if d.family == family]

    if not designs:
        log.warning("No ready designs found. Check benchmark collateral paths.")
        log.info(registry.summary())
        sys.exit(0)

    log.info("Running mode=%s on %d design(s)", mode, len(designs))

    # Load CA config
    ca_cfg = {}
    try:
        with open(ca_config) as f:
            ca_cfg = yaml.safe_load(f)
    except OSError:
        log.warning("CA config not found at %s; using defaults.", ca_config)

    global_cfg  = ca_cfg.get("global", {})
    rule_sets   = ca_cfg.get("rule_sets", {})
    rule_params = ca_cfg.get("rule_params", {})
    rule_search = ca_cfg.get("rule_search", {})

    runner = OpenROADRunner(openroad_bin=openroad, log_dir=output_dir / "logs")
    writer = CSVResultWriter(output_dir / "tables")

    family_map = {d.name: d.family for d in designs}

    if mode == "baseline":
        flow    = BaselineFlow(runner, output_dir)
        metrics = {}
        results = []
        for d in designs:
            _, m = flow.run(d)
            results.append(m)
        metrics["baseline"] = results
        csv_path = writer.write_all(metrics, "results_baseline.csv", family_map)
        writer.write_summary(csv_path)
        _plot_comparison(output_dir, csv_path)

    elif mode == "full":
        full_cfg = rule_sets.get("full_ca", {})
        if not full_cfg.get("enabled", True):
            log.error("full_ca rule-set is disabled in config.")
            sys.exit(1)

        baseline_flow = BaselineFlow(runner, output_dir)
        ca_flow = CAFlow(
            runner         = runner,
            output_dir     = output_dir,
            rule_set_cfg   = full_cfg,
            rule_params    = rule_params,
            grid_rows      = global_cfg.get("grid_resolution", 64),
            grid_cols      = global_cfg.get("grid_resolution", 64),
            neighborhood   = global_cfg.get("neighborhood", "moore"),
            convergence_eps = global_cfg.get("convergence_eps", 1e-5),
            seed           = global_cfg.get("seed", seed),
        )

        results = {"baseline": [], "full_ca": []}
        for d in designs:
            _, bm      = baseline_flow.run(d)
            fp, cm, ev = ca_flow.run(d, rule_set_name="full_ca")
            results["baseline"].append(bm)
            results["full_ca"].append(cm)

            # Render floorplan figure
            ren = FloorplanRenderer(output_dir / "figures")
            ren.render(fp, title=f"{d.name} — CA full")

        csv_path = writer.write_all(results, "results_full.csv", family_map)
        writer.write_summary(csv_path)
        _plot_comparison(output_dir, csv_path)

    elif mode == "ablation":
        study = AblationStudy(
            rule_sets_cfg = rule_sets,
            rule_params   = rule_params,
            global_cfg    = global_cfg,
            runner        = runner,
            output_dir    = output_dir,
        )
        ablation_results = study.run(designs)
        csv_path = writer.write_all(ablation_results, "results_ablation.csv", family_map)
        writer.write_summary(csv_path)
        _plot_ablation(output_dir, csv_path)

    elif mode == "rule-search":
        searcher = RuleSearcher(
            search_cfg  = rule_search,
            rule_params = rule_params,
            global_cfg  = global_cfg,
            runner      = runner,
            output_dir  = output_dir,
        )
        searcher.search(designs)

    log.info("Done. Results in %s", output_dir)


def _plot_comparison(output_dir: Path, csv_path: Path) -> None:
    try:
        p = ComparisonChartPlotter(output_dir / "figures")
        p.plot_from_csv(csv_path)
    except Exception as e:
        log.warning("Plotting failed: %s", e)


def _plot_ablation(output_dir: Path, csv_path: Path) -> None:
    try:
        p = ComparisonChartPlotter(output_dir / "figures")
        p.plot_ablation(csv_path)
    except Exception as e:
        log.warning("Ablation plot failed: %s", e)


if __name__ == "__main__":
    cli()
