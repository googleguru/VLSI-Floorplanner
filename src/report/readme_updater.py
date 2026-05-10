"""Auto-update README.md with concise results and figures.

The updater replaces tagged sections between:
  <!-- CA_RESULTS_START -->  and  <!-- CA_RESULTS_END -->
  <!-- CA_FIGURES_START -->  and  <!-- CA_FIGURES_END -->

leaving all other README content intact.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Optional

import click

from .markdown_generator import results_table_md, summary_table_md, figure_embed_md

log = logging.getLogger(__name__)

_SECTION_RE = re.compile(
    r"(<!-- CA_RESULTS_START -->).*?(<!-- CA_RESULTS_END -->)",
    re.DOTALL,
)
_FIG_RE = re.compile(
    r"(<!-- CA_FIGURES_START -->).*?(<!-- CA_FIGURES_END -->)",
    re.DOTALL,
)


class ReadmeUpdater:
    def __init__(self, readme_path: Path) -> None:
        self.readme_path = Path(readme_path)

    def update(
        self,
        results_dir: Path,
        figures_dir: Path,
    ) -> None:
        if not self.readme_path.exists():
            log.warning("README not found at %s", self.readme_path)
            return

        text = self.readme_path.read_text()

        # Results section
        summary_csv = results_dir / "summary.csv"
        results_csv = results_dir / "results_ablation.csv"
        if not results_csv.exists():
            results_csv = results_dir / "results_full.csv"
        if not results_csv.exists():
            results_csv = results_dir / "results_baseline.csv"

        results_block = (
            f"\n{summary_table_md(summary_csv)}\n"
            f"**Full results:**\n\n"
            f"{results_table_md(results_csv)}\n"
        )
        if _SECTION_RE.search(text):
            text = _SECTION_RE.sub(
                r"\1" + results_block + r"\2",
                text,
            )
        else:
            log.warning("CA_RESULTS tags not found in README. Appending.")
            text += (
                f"\n<!-- CA_RESULTS_START -->\n{results_block}<!-- CA_RESULTS_END -->\n"
            )

        # Figures section
        fig_block = f"\n{figure_embed_md(figures_dir)}\n"
        if _FIG_RE.search(text):
            text = _FIG_RE.sub(r"\1" + fig_block + r"\2", text)
        else:
            text += f"\n<!-- CA_FIGURES_START -->\n{fig_block}<!-- CA_FIGURES_END -->\n"

        self.readme_path.write_text(text)
        log.info("README updated: %s", self.readme_path)


@click.command()
@click.option("--results",  required=True, type=click.Path(), help="Tables directory.")
@click.option("--figures",  required=True, type=click.Path(), help="Figures directory.")
@click.option("--readme",   default="README.md", help="README.md path.")
def cli(results: str, figures: str, readme: str) -> None:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    updater = ReadmeUpdater(Path(readme))
    updater.update(Path(results), Path(figures))


if __name__ == "__main__":
    cli()
