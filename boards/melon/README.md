# 🍈 NextMicon Melon 🍈

High-density NextMicon FPGA board placement study.

## Target

- FPGA: AMD Artix-7 `XC7A100T-1FGG676C`
- GPIO: 256 pins, 3.3 V logic
- GPIO connectors: eight 2x24, 2.54 mm headers
- GPIO geometry: 32 groups of eight, using the same contiguous 2x4 windows as Cherry and Grape
- Configuration: protected boot image followed by an ICAPE2/WBSTAR/IPROG user image
- Default user selection: back-side `DEFAULT_USER` solder jumper
- Clock: independent onboard oscillator; not required to match Cherry or Grape
- Placement PCB: 150 mm x 120 mm, six layers, deliberately unrouted

## Placement

The current [`board/src/melon.kicad_pcb`](board/src/melon.kicad_pcb) is a
placement-only board with no schematic nets, tracks, vias, planes, or copper
zones. The eight headers are arranged two per row across four rows. Adjacent
header rows use 7.62 mm center spacing, leaving one 2.54 mm pin-row interval
between their bodies. They provide
32 GPIO positions each, for 256 GPIOs total;
the remaining 16 contacts on every 2x24 header are reserved for GND, 3.3 V and
board utility connections following the Cherry grouping pattern.

The checked FPGA-to-header allocation is [`board/pinout.csv`](board/pinout.csv).
It is generated from AMD's production `xc7a100tfgg676pkg.csv` by
[`board/tools/generate_pinout.py`](board/tools/generate_pinout.py).

Regulator footprints are placement reservations only. Parts and thermal/current
ratings must be selected from a final power estimate before fabrication.

## Regeneration

```bash
python3 board/tools/generate_pinout.py
python3 board/tools/generate_placement.py
kicad-cli pcb drc --all-track-errors \
  -o board/placement-drc.rpt board/src/melon.kicad_pcb
```
