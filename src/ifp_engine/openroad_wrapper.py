"""OpenROAD subprocess wrapper.

Calls the `openroad` binary with a generated Tcl script.
Falls back gracefully when OpenROAD is not installed (simulation mode).
"""
from __future__ import annotations

import dataclasses
import logging
import shutil
import subprocess
import time
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

_OPENROAD = shutil.which("openroad")


@dataclasses.dataclass
class IFPResult:
    design_name:  str
    success:      bool
    runtime_s:    float
    def_path:     Optional[Path] = None
    log_path:     Optional[Path] = None
    error_msg:    str = ""
    simulated:    bool = False    # True when OpenROAD was not available


class OpenROADRunner:
    """Runs OpenROAD with a Tcl script and captures output."""

    def __init__(
        self,
        openroad_bin: Optional[str] = None,
        timeout_s: int = 600,
        log_dir: Optional[Path] = None,
    ) -> None:
        self.openroad_bin = openroad_bin or _OPENROAD
        self.timeout_s    = timeout_s
        self.log_dir      = Path(log_dir) if log_dir else Path("outputs/logs")
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def run(self, tcl_path: Path, design_name: str) -> IFPResult:
        log_path = self.log_dir / f"{design_name}_ifp.log"

        if self.openroad_bin is None:
            log.warning(
                "OpenROAD not found on PATH. Running in simulation mode "
                "for design '%s'. Install OpenROAD to get real results.",
                design_name,
            )
            return self._simulate(tcl_path, design_name, log_path)

        t0 = time.perf_counter()
        try:
            with open(log_path, "w") as logf:
                result = subprocess.run(
                    [self.openroad_bin, tcl_path],
                    stdout=logf,
                    stderr=subprocess.STDOUT,
                    timeout=self.timeout_s,
                )
            elapsed = time.perf_counter() - t0
            success = result.returncode == 0

            if not success:
                err = _tail(log_path, 20)
                log.error("OpenROAD failed for %s (rc=%d):\n%s",
                           design_name, result.returncode, err)
                return IFPResult(design_name, False, elapsed,
                                 log_path=log_path, error_msg=err)

            # Extract written DEF path from the Tcl
            def_path = _extract_def_path(tcl_path)
            log.info("OpenROAD OK  %-25s  %.2fs", design_name, elapsed)
            return IFPResult(design_name, True, elapsed,
                             def_path=def_path, log_path=log_path)

        except subprocess.TimeoutExpired:
            elapsed = time.perf_counter() - t0
            msg = f"OpenROAD timed out after {self.timeout_s}s"
            log.error(msg)
            return IFPResult(design_name, False, elapsed, log_path=log_path, error_msg=msg)

        except Exception as exc:
            elapsed = time.perf_counter() - t0
            log.error("Unexpected error running OpenROAD: %s", exc)
            return IFPResult(design_name, False, elapsed, error_msg=str(exc))

    # ── simulation mode ───────────────────────────────────────────────────────

    def _simulate(self, tcl_path: Path, design_name: str, log_path: Path) -> IFPResult:
        """Write a simulation-mode DEF stub so the pipeline can continue."""
        t0 = time.perf_counter()
        def_path = _extract_def_path(tcl_path)

        sim_note = (
            f"# SIMULATION MODE: OpenROAD not available\n"
            f"# Tcl script: {tcl_path}\n"
        )
        log_path.write_text(sim_note)

        if def_path and not def_path.exists():
            def_path.parent.mkdir(parents=True, exist_ok=True)
            # Write a minimal valid DEF so downstream parsers don't crash
            def_path.write_text(
                f"VERSION 5.8 ;\n"
                f"DESIGN {design_name} ;\n"
                f"UNITS DISTANCE MICRONS 1000 ;\n"
                f"DIEAREA ( 0 0 ) ( 200000 200000 ) ;\n"
                f"COMPONENTS 0 ;\nEND COMPONENTS\n"
                f"NETS 0 ;\nEND NETS\n"
                f"END DESIGN\n"
            )

        elapsed = time.perf_counter() - t0
        return IFPResult(
            design_name, True, elapsed,
            def_path=def_path, log_path=log_path, simulated=True,
        )


# ── helpers ───────────────────────────────────────────────────────────────────

def _extract_def_path(tcl_path: Path) -> Optional[Path]:
    """Parse 'write_def <path>' from the Tcl script."""
    try:
        for line in tcl_path.read_text().splitlines():
            s = line.strip()
            if s.startswith("write_def "):
                return Path(s.split(None, 1)[1].strip())
    except OSError:
        pass
    return None


def _tail(path: Path, n: int) -> str:
    try:
        lines = path.read_text().splitlines()
        return "\n".join(lines[-n:])
    except OSError:
        return ""
