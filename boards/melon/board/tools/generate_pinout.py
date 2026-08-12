#!/usr/bin/env python3
"""Generate the 256-GPIO Melon pinout from AMD XC7A100T-FGG676 data."""

from __future__ import annotations

import csv
from pathlib import Path


HERE = Path(__file__).resolve().parent
FPGA_ROOT = HERE.parents[3]
PACKAGE = FPGA_ROOT / "parts/amd/pinouts/a7all/xc7a100tfgg676pkg.csv"
OUTPUT = HERE.parent / "pinout.csv"


def rows() -> list[dict[str, str]]:
    lines = PACKAGE.read_text(encoding="utf-8").splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith("Pin,Pin Name,"))
    return [row for row in csv.DictReader(lines[start:]) if row.get("Pin") and row["Pin"] != "Total Number of Pins"]


def connector_pad(index: int) -> tuple[str, int, int, str]:
    connector = f"J{index // 32 + 2}"
    within = index % 32
    group = within // 8
    bit = within % 8
    position = 5 + group * 5 + bit % 4
    row = "inner" if bit < 4 else "outer"
    pad = position * 2 - 1 if row == "inner" else position * 2
    return connector, position, pad, row


def main() -> None:
    package = rows()
    gpio: list[dict[str, str]] = []
    for bank in ("13", "15", "16", "34", "35"):
        candidates = [row for row in package if row["Bank"] == bank and row["I/O Type"] == "HR" and row["Pin Name"].startswith("IO_")]
        if len(candidates) != 50:
            raise ValueError(f"bank {bank}: expected 50 HR I/O, found {len(candidates)}")
        gpio.extend(candidates)
    # Six upper Bank-14 pins not used by QSPI, clock, USB or board controls.
    bank14_balls = ("R26", "P26", "T22", "R22", "T23", "R23")
    by_ball = {row["Pin"]: row for row in package}
    gpio.extend(by_ball[ball] for ball in bank14_balls)
    if len(gpio) != 256 or len({row["Pin"] for row in gpio}) != 256:
        raise ValueError("GPIO selection is not 256 unique package balls")

    with OUTPUT.open("w", newline="", encoding="utf-8") as output:
        writer = csv.writer(output)
        writer.writerow(("channel", "signal", "fpga_ball", "fpga_pin_name", "bank", "connector", "position", "connector_pad", "row", "group"))
        for index, package_pin in enumerate(gpio):
            connector, position, pad, header_row = connector_pad(index)
            writer.writerow((index + 1, f"GPIO_{index + 1:03d}", package_pin["Pin"], package_pin["Pin Name"], package_pin["Bank"], connector, position, pad, header_row, index // 8 + 1))
    print(f"wrote {OUTPUT} with 256 GPIOs in 32 groups")


if __name__ == "__main__":
    main()
