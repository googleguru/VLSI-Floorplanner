"""Generate a minimal stub DEF and unit LEF from a mapped Verilog netlist.

This provides a floorplan-compatible DEF for ISCAS designs when OpenROAD
is not available for full elaboration. The stub contains correct UNITS,
DIEAREA, and COMPONENTS sections required by initialize_floorplan.
"""
from __future__ import annotations

import re
from pathlib import Path


_UNIT_LEF_TEMPLATE = """\
VERSION 5.8 ;
BUSBITCHARS "[]" ;
DIVIDERCHAR "/" ;
UNITS
  DATABASE MICRONS 1000 ;
END UNITS
SITE unit
  SYMMETRY Y ;
  CLASS CORE ;
  SIZE 0.19 BY 1.4 ;
END unit
END LIBRARY
"""

_INST_RE = re.compile(r"^\s*(\w+)\s+(\w+)\s*\(", re.MULTILINE)


def write_stub_def(
    design_name: str,
    verilog_path: Path,
    def_path: Path,
    lef_path: Path,
    die_area: tuple = (0, 0, 500000, 500000),   # in DEF units (1000/µm)
    core_area: tuple = (10000, 10000, 490000, 490000),
    db_units: int = 1000,
) -> None:
    """Write <design>.def and <design>.lef stubs for ISCAS designs."""

    # Collect cell instances from Verilog
    instances: list[tuple[str, str]] = []  # (cell_type, inst_name)
    try:
        text = verilog_path.read_text()
        for m in _INST_RE.finditer(text):
            instances.append((m.group(1), m.group(2)))
    except OSError:
        pass

    lef_path.write_text(_UNIT_LEF_TEMPLATE)

    with open(def_path, "w") as f:
        f.write(f"VERSION 5.8 ;\n")
        f.write(f"DIVIDERCHAR \"/\" ;\n")
        f.write(f"BUSBITCHARS \"[]\" ;\n")
        f.write(f"DESIGN {design_name} ;\n")
        f.write(f"UNITS DISTANCE MICRONS {db_units} ;\n\n")
        f.write(f"DIEAREA ( {die_area[0]} {die_area[1]} ) ( {die_area[2]} {die_area[3]} ) ;\n\n")

        if instances:
            f.write(f"COMPONENTS {len(instances)} ;\n")
            x, y = core_area[0] + 200, core_area[1] + 200
            step = 400
            for ctype, iname in instances:
                f.write(f"   - {iname} {ctype} + PLACED ( {x} {y} ) N ;\n")
                x += step
                if x > core_area[2] - 200:
                    x = core_area[0] + 200
                    y += step
            f.write("END COMPONENTS\n\n")
        else:
            f.write("COMPONENTS 0 ;\nEND COMPONENTS\n\n")

        f.write("NETS 0 ;\nEND NETS\n\n")
        f.write("END DESIGN\n")
