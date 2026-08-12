#!/usr/bin/env python3
"""Generate the XC7S50-CSGA324 KiCad symbol from AMD's package CSV."""

from __future__ import annotations

import csv
from pathlib import Path


HERE = Path(__file__).resolve().parent
FPGA_ROOT = HERE.parents[3]
PACKAGE = FPGA_ROOT / "parts/amd/pinouts/s7all/xc7s50csga324pkg.csv"
OUTPUT = HERE.parent / "src/grape-fpga.kicad_sym"
NAME = "XC7S50-CSGA324"


def q(value: str) -> str:
    return '"' + value.replace('\\', '\\\\').replace('"', '\\"') + '"'


def rows() -> list[dict[str, str]]:
    lines = PACKAGE.read_text(encoding="utf-8").splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith("Pin,Pin Name,"))
    return [row for row in csv.DictReader(lines[start:]) if row.get("Pin") and row["Pin"] != "Total Number of Pins"]


def pin_type(row: dict[str, str]) -> str:
    name = row["Pin Name"]
    if name == "GND" or name.startswith("VCC") or name.startswith("GND"):
        return "power_in"
    if name.startswith(("TDO", "DONE")):
        return "output"
    if name.startswith(("TCK", "TDI", "TMS", "M0_", "M1_", "M2_", "PROGRAM_B", "CFGBVS")):
        return "input"
    return "bidirectional"


def pin_line(row: dict[str, str], x: float, y: float, angle: int) -> str:
    return (
        f'      (pin {pin_type(row)} line (at {x:.2f} {y:.2f} {angle}) (length 2.54)\n'
        f'        (name {q(row["Pin Name"])} (effects (font (size 1.0 1.0))))\n'
        f'        (number {q(row["Pin"])} (effects (font (size 1.0 1.0))))\n'
        '      )'
    )


def main() -> None:
    package_rows = rows()
    if len(package_rows) != 324:
        raise ValueError(f"expected 324 package balls, found {len(package_rows)}")

    units: list[tuple[str, list[dict[str, str]]]] = []
    for bank in (14, 15, 16, 34, 35):
        units.append((f"BANK {bank}", [row for row in package_rows if row["Bank"] == str(bank) and row["I/O Type"] == "HR"]))
    assigned = {row["Pin"] for _, unit_rows in units for row in unit_rows}
    units.append(("POWER / CONFIG / ADC", [row for row in package_rows if row["Pin"] not in assigned]))
    if len({row["Pin"] for _, unit_rows in units for row in unit_rows}) != 324:
        raise ValueError("unit assignment does not cover every unique package ball")

    text = [
        '(kicad_symbol_lib',
        '  (version 20231120)',
        '  (generator "generate_fpga_symbol.py")',
        f'  (symbol {q(NAME)}',
        '    (pin_names (offset 1.0))',
        '    (exclude_from_sim no)',
        '    (in_bom yes)',
        '    (on_board yes)',
        '    (property "Reference" "U" (at 0 2.54 0) (effects (font (size 1.27 1.27))))',
        f'    (property "Value" {q(NAME)} (at 0 0 0) (effects (font (size 1.27 1.27))))',
        '    (property "Footprint" "Package_BGA:Xilinx_CSGA324" (at 0 -2.54 0) (effects (font (size 1.27 1.27)) hide))',
        '    (property "Datasheet" "https://docs.amd.com/r/en-US/ds189-spartan-7-data-sheet" (at 0 -5.08 0) (effects (font (size 1.27 1.27)) hide))',
        '    (property "Description" "AMD Spartan-7 XC7S50, CSGA324 package" (at 0 -7.62 0) (effects (font (size 1.27 1.27)) hide))',
    ]
    for unit_number, (title, unit_rows) in enumerate(units, start=1):
        left = unit_rows[: (len(unit_rows) + 1) // 2]
        right = unit_rows[len(left):]
        height = max(len(left), len(right)) * 2.54 + 5.08
        top = -height / 2
        bottom = height / 2
        text.extend((
            f'    (symbol {q(f"{NAME}_{unit_number}_1")}',
            f'      (rectangle (start -15.24 {top:.2f}) (end 15.24 {bottom:.2f})',
            '        (stroke (width 0) (type default)) (fill (type background)))',
            f'      (text {q(title)} (at 0 {top + 1.27:.2f} 0) (effects (font (size 1.27 1.27) (bold yes))))',
        ))
        for index, row in enumerate(left):
            text.append(pin_line(row, -17.78, top + 3.81 + index * 2.54, 0))
        for index, row in enumerate(right):
            text.append(pin_line(row, 17.78, top + 3.81 + index * 2.54, 180))
        text.append('    )')
    text.extend(('  )', ')', ''))
    OUTPUT.write_text("\n".join(text), encoding="utf-8")
    print(f"wrote {OUTPUT} with {len(units)} units and {len(package_rows)} pins")


if __name__ == "__main__":
    main()
