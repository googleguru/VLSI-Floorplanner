"""Helpers for generating make_rows and make_tracks Tcl commands."""
from __future__ import annotations

from typing import List, Optional


def make_rows_tcl(
    site: str,
    additional_sites: Optional[List[str]] = None,
    flip_alternate: bool = False,
    row_parity: Optional[str] = None,
) -> str:
    """Emit a make_rows Tcl command."""
    parts = [f"make_rows -site {site}"]
    for s in (additional_sites or []):
        parts.append(f"-additional_sites {s}")
    if flip_alternate:
        parts.append("-flip_alternate_rows")
    if row_parity in ("even", "odd"):
        parts.append(f"-row_parity {row_parity}")
    return " ".join(parts)


def make_tracks_tcl(layers: List[dict]) -> str:
    """Emit make_tracks Tcl commands for each layer dict."""
    lines = []
    for t in layers:
        layer   = t.get("layer",    "M1")
        x_off   = t.get("x_offset", 0)
        x_pitch = t.get("x_pitch",  0.1)
        y_off   = t.get("y_offset", 0)
        y_pitch = t.get("y_pitch",  0.1)
        lines.append(
            f"make_tracks {layer} "
            f"-x_offset {x_off} -x_pitch {x_pitch} "
            f"-y_offset {y_off} -y_pitch {y_pitch}"
        )
    return "\n".join(lines)
