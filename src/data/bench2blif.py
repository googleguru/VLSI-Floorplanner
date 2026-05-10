"""Minimal ISCAS .bench to BLIF converter.

Supports: INPUT, OUTPUT, NOT, AND, OR, NAND, NOR, XOR, XNOR, DFF, BUF, FROM
"""
from __future__ import annotations

from pathlib import Path


def convert(bench_path: Path, blif_path: Path) -> None:
    inputs, outputs, gates, dffs = [], [], [], []

    with open(bench_path) as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            up = line.upper()
            if up.startswith("INPUT("):
                inputs.append(_paren(line))
            elif up.startswith("OUTPUT("):
                outputs.append(_paren(line))
            elif "DFF(" in up:
                out = line.split("=")[0].strip()
                inp = _paren(line)
                dffs.append((out, inp))
            elif "=" in line:
                out  = line.split("=")[0].strip()
                rhs  = line.split("=", 1)[1].strip()
                gate = rhs.split("(")[0].upper()
                ins  = [x.strip() for x in _paren(rhs).split(",")]
                gates.append((out, gate, ins))

    top = blif_path.stem
    with open(blif_path, "w") as f:
        f.write(f".model {top}\n")
        f.write(f".inputs {' '.join(inputs)}\n")
        f.write(f".outputs {' '.join(outputs)}\n\n")

        for out, gate, ins in gates:
            _write_gate(f, out, gate, ins)

        for q, d in dffs:
            f.write(f".latch {d} {q} re clk 0\n")

        f.write(".end\n")


def _paren(s: str) -> str:
    return s[s.index("(") + 1: s.rindex(")")]


def _write_gate(f, out: str, gate: str, ins: list) -> None:
    n = len(ins)
    if gate in ("BUF", "FROM"):
        f.write(f".names {ins[0]} {out}\n1 1\n")
    elif gate == "NOT":
        f.write(f".names {ins[0]} {out}\n0 1\n")
    elif gate == "AND":
        cover = "1" * n + " 1"
        f.write(f".names {' '.join(ins)} {out}\n{cover}\n")
    elif gate == "NAND":
        cover = "1" * n + " 0"
        f.write(f".names {' '.join(ins)} {out}\n")
        for i in range(n):
            f.write("0" * i + "-" + "0" * (n - i - 1) + " 1\n")
    elif gate == "OR":
        f.write(f".names {' '.join(ins)} {out}\n")
        for i in range(n):
            f.write("-" * i + "1" + "-" * (n - i - 1) + " 1\n")
    elif gate == "NOR":
        cover = "0" * n + " 1"
        f.write(f".names {' '.join(ins)} {out}\n{cover}\n")
    elif gate == "XOR":
        f.write(f".names {' '.join(ins)} {out}\n")
        f.write("01 1\n10 1\n")
    elif gate == "XNOR":
        f.write(f".names {' '.join(ins)} {out}\n")
        f.write("00 1\n11 1\n")
    else:
        # Unknown gate — emit a buffer as safe fallback
        f.write(f".names {ins[0]} {out}\n1 1\n")
