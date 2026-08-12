# Development guide

KiCad Version = 10.0.3

```
boards/cherry/
├── board/      # KiCad project, libraries, and fabrication outputs
├── breakout/   # Breakout and factory-test fixture
├── firmware/   # FPGA HDL and constraints
└── README.md
```

## 1. Install KiCad

```bash
$ sudo add-apt-repository --yes ppa:kicad/kicad-10.0-releases
$ sudo apt update
$ sudo apt install --install-recommends kicad
$ kicad-cli version
10.0.3
```

## 2. Setup KiCad MCP

TBD

## 3. Open KiCad project

```
$ kicad boards/cherry/board/src/cherry.kicad_pro
```

## 4. Render board image

```bash
$ kicad-cli pcb render -o boards/cherry/cherry.png \
    --side top --width 1440 --height 720 --zoom 1.8 --quality high \
    boards/cherry/board/src/cherry.kicad_pcb
```

# Development Notes

Commands for regenerating documents and fabrication data.
All commands run from the repository root.

## Requirements

- KiCad 10.0+ (`kicad-cli` in PATH)
- On WSL: the Linux `kicad-cli` may fail to read this project's file format.
  Use the Windows binary instead:

```bash
alias kicad-cli='"/mnt/c/Program Files/KiCad/10.0/bin/kicad-cli.exe"'
# Pass Windows-style paths via: $(wslpath -w <path>)
```

## Design checks (run before committing)

```bash
# ERC (expect 0 violations)
kicad-cli sch erc --severity-all -o erc.rpt src/cherry.kicad_sch

# DRC + schematic parity (expect 0 parity issues; baseline warnings are
# 11x lib_footprint_mismatch (intentional local overrides) + 2x silk_edge_clearance)
kicad-cli pcb drc --schematic-parity --severity-all -o drc.rpt src/cherry.kicad_pcb
```

## PDF / images (committed at repo root)

```bash
# Schematic PDF
kicad-cli sch export pdf -o schematic.pdf src/cherry.kicad_sch

# Board PDF (one page per layer, board outline on every page)
kicad-cli pcb export pdf --mode-multipage \
  -l "F.Cu,In1.Cu,In2.Cu,B.Cu,F.Silkscreen,B.Silkscreen,F.Mask,B.Mask,F.Fab,B.Fab" \
  --cl "Edge.Cuts" --include-border-title \
  -o board.pdf src/cherry.kicad_pcb

# Board render for README
kicad-cli pcb render --side top --width 1432 --height 704 \
  -o doc/img/board.png src/cherry.kicad_pcb
```

## Fabrication data (JLCPCB PCBA)

Output goes to `out/` (gitignored). Three deliverables: gerber zip, BOM CSV, CPL CSV.

### 1. Gerbers + drill

```bash
mkdir -p out/gerber

kicad-cli pcb export gerbers \
  -l "F.Cu,In1.Cu,In2.Cu,B.Cu,F.Silkscreen,B.Silkscreen,F.Mask,B.Mask,F.Paste,B.Paste,Edge.Cuts" \
  --no-x2 --subtract-soldermask --use-drill-file-origin \
  -o out/gerber src/cherry.kicad_pcb

kicad-cli pcb export drill \
  --format excellon --excellon-units mm --excellon-separate-th \
  --generate-map --map-format gerberx2 \
  -o out/gerber src/cherry.kicad_pcb

(cd out && zip -r cherry-gerber.zip gerber)
```

### 2. BOM (JLC format)

LCSC part numbers live in an `LCSC` field on each schematic symbol (populated
2026-08-10). Intentionally blank fields:

- `X1` (Abracon ASE XO): not stocked at LCSC - use JLC Global Sourcing /
  consignment, or pick an LCSC-stocked 12 MHz 3225 XO (+/-25 ppm or better).
- `L1-L2`: select a 0805 1 uH inductor with Isat >= 1.5 A at order time.
- `D1-D4`: pick LED colors (0603).
- `J2-J6`: generic headers, normally left unpopulated.

Substitutions used for LCSC availability (same footprint / spec family):
`U2` = C179173 (W25Q32JVSSIQ; SSIM is not listed on LCSC),
`FB1-FB2` = C85837 (BLM21AG601SN1D standard grade; BOM names SH1D).

```bash
kicad-cli sch export bom \
  --fields "Value,Reference,Footprint,LCSC" \
  --labels "Comment,Designator,Footprint,LCSC Part #" \
  --group-by "Value,Footprint" --exclude-dnp \
  -o out/cherry-bom.csv src/cherry.kicad_sch
```

### 3. CPL (component placement)

```bash
kicad-cli pcb export pos \
  --format csv --units mm --side front \
  --use-drill-file-origin --exclude-dnp --smd-only \
  -o out/cherry-cpl.csv src/cherry.kicad_pcb

# Rename header to JLC column names
sed -i '1s/.*/Designator,Val,Package,Mid X,Mid Y,Rotation,Layer/' out/cherry-cpl.csv
```

### Ordering notes

- 4-layer stackup: JLC04161H-7628 (matches the board's stackup settings, ~1.6 mm).
- All SMD parts are on the top side (single-side assembly). Pin headers
  (J2-J6) are through-hole: order unpopulated or add JLC hand-soldering service.
- Component rotations for polarized parts (U1 pin 1, LEDs D1-D4, D5/U4/U5,
  U3 BGA) must be verified in the JLCPCB order preview - JLC rotation
  conventions differ from KiCad for some packages.
- FT2232HL / iCE40 are Extended parts (loading fee applies); most 0402/0805
  passives map to Basic parts.
