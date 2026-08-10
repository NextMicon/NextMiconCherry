# 🍇 NextMicon Grape 🍇

NextMicon Grape is a FPGA Board for cyuukyusya.
Xilinx Artix-7 has more LUT cores and more fast signal processing units.

## Current design

- FPGA: AMD Artix-7 `XC7A35T-1FTG256C`
- Configuration: W25Q128JV 128-Mbit QSPI, four 4-MiB image slots
- Boot: Golden image at address zero, then `WBSTAR`/`IPROG` through `ICAPE2`
- USB: USB-C Full-Speed device connected directly to 3.3-V FPGA I/O
- Clock: 48 MHz oscillator on an SRCC input
- Power: USB 5 V to sequenced 1.0 V, 1.8 V and 3.3 V TPS62A02 rails
- I/O: 56 named 3.3-V GPIO signals on two 2x20 headers
- Recovery: external six-pin JTAG header, `PROGRAM_B`, and true cold-reset
- FPGA package and decoupling: FTG256, based on AMD UG475/UG483

The KiCad project is in [`pcb/src`](pcb/src).  The 84 mm x 64 mm, four-layer
PCB currently contains a complete component placement and board outline only;
routing, vias and copper zones have deliberately not been started yet.

- [Front placement PDF](pcb/board.pdf)
- [Back placement PDF](pcb/board-back.pdf)

## Important design choices

`M[2:0]` is strapped to `001` for Master SPI.  All VCCO banks, the
configuration bank, and the flash operate at 3.3 V; `CFGBVS` is therefore tied
to 3.3 V.  The two-bit `IMAGE` switch is normal FPGA GPIO sampled by the
Golden image—it is not a direct configuration-mode selector.

`JP1 GOLDEN_LOCK` pulls the flash `/WP/IO2` signal low.  Fit the jumper for
hardware-assisted x1-SPI Golden protection after setting the Winbond block and
status-register protection bits.  Remove it for factory update or future x4
QSPI operation.  Firmware must keep the FPGA IO2 pin high-impedance while the
jumper is fitted.

The TPS22917 load switch limits USB attach inrush into the regulator input
capacitors.  Its CT capacitor `C2` returns to `VBUS_FUSED` as required by the
device topology and is deliberately marked `TUNE`; its final value must be
selected from measured inrush and rise time.  The present design must remain
inside the current advertised by the connected USB-C source.  High-power user
images may require a later auxiliary-power option.

The Master-SPI mode straps and `PUDC_B` use 1-kohm resistors.  Flash IO2 and
IO3 use 4.7-kohm pull-ups for x4 configuration.  The XADC uses its on-chip
reference, with `VREFP`/`VREFN` returned locally to filtered analog ground.

## Generate and check

Requires KiCad 10.0.x and Python 3.  The generated schematic embeds its symbols.

```bash
python3 grape/pcb/tools/generate_schematic.py
kicad-cli sch upgrade --force grape/pcb/src/grape.kicad_sch
kicad-cli sch erc --severity-all \
  -o grape/pcb/erc.rpt grape/pcb/src/grape.kicad_sch
kicad-cli sch export pdf \
  -o grape/pcb/schematic.pdf grape/pcb/src/grape.kicad_sch
python3 grape/pcb/tools/generate_board.py
```

The board generator synchronizes all 136 schematic footprints and their nets,
places 112 footprints on the front and 24 FPGA power-decoupling footprints on
the back, and leaves every net unrouted.  PCB DRC therefore reports the
expected unconnected-pad items until routing begins.

## Before PCB fabrication

- Recheck every FTG256 ball against the AMD package pin file and UG475.
- Run Xilinx Power Estimator with the intended maximum application image.
- Validate regulator stability, inductors, capacitor DC bias and startup order.
- Tune USB series resistors and load-switch rise time from measurements.
- Decide whether x1 physical Golden protection or x4 boot speed is the product
  default.
- Extend and validate the OSS bitstream writer for configuration rate, x4 SPI,
  CRC watchdog and automatic fallback.

## Primary references

- [AMD UG470: 7 Series FPGAs Configuration User Guide](https://docs.amd.com/v/u/en-US/ug470_7Series_Config)
- [AMD UG475: 7 Series FPGAs Packaging and Pinout](https://docs.amd.com/v/u/en-US/ug475_7Series_Pkg_Pinout)
- [AMD UG480: 7 Series XADC User Guide](https://docs.amd.com/r/en-US/ug480_7Series_XADC)
- [AMD UG483: 7 Series FPGAs PCB Design Guide](https://docs.amd.com/v/u/en-US/ug483_7Series_PCB)
- [TI TPS62A02 data sheet](https://www.ti.com/lit/ds/symlink/tps62a02.pdf)
- [TI TPS22917 data sheet](https://www.ti.com/lit/ds/symlink/tps22917.pdf)
- [Winbond W25Q128JV data sheet](https://www.winbond.com/resource-files/w25q128jv%20revf%2003272018%20plus.pdf)
