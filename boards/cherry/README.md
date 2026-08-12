# 🍒 NextMicon Cherry 🍒

FPGA Board for Beginners

## Repository layout

- [`board`](board/): KiCad design and fabrication outputs
- [`breakout`](breakout/): PMod breakout board
- [`firmware`](firmware/): FPGA HDL and constraints

## Schematic

![](cherry.png)

![](../../doc/img/diagram.dio.svg)

## Specs

- FPGA: Lattice iCE40HX8K-BG121 (7680 LUTs, 9x9mm, 0.8mm pitch)
- GPIO: 64 pins (3.3V logic)
- PLL: 2x sysCLOCK PLL, external reference inputs broken out on J3 position 22 (PLL0_IN/PLL1_IN)
- Clock: 48MHz
- Flash: 32Mbit SPI Flash (3.5 MiB user-data area)
- Power: USB 5V → 3.3V → 1.2V
- Signal: 3.3V
- USB ESD Protection
- Switch: CRESET_B reset / USER buttons
- LED: PWR / PROG / USER0-USER3
- Board: 61mm x 31mm, 4-layer FR4

## Pinout

J2 and J3 are standard 2x24 headers. Each connector position `k` (1..24) has an
inner-row pad `2k-1` (odd) and an outer-row pad `2k` (even); the two rows carry
independent signals.

GPIOs are grouped in blocks of eight: D0-D3 sit on the inner row and D4-D7 sit
directly opposite on the outer row of the same four positions, so every block
forms one contiguous 2x4 window flanked by GND (inner) / 3V3 (outer) columns.
J2 carries GPIO_1..32 and J3 carries GPIO_33..64.

J2 (bottom edge, position 1 = USB side):

| Position | Inner row (odd pads) | Outer row (even pads) |
| -------- | -------------------- | --------------------- |
| 1        | 5V                   | 5V                    |
| 2        | 3V3                  | 3V3                   |
| 3        | CRESET_B             | 3V3                   |
| 4        | GND                  | 3V3                   |
| 5-8      | GPIO_1..4            | GPIO_5..8             |
| 9        | GND                  | 3V3                   |
| 10-13    | GPIO_9..12           | GPIO_13..16           |
| 14       | GND                  | 3V3                   |
| 15-18    | GPIO_17..20          | GPIO_21..24           |
| 19       | GND                  | 3V3                   |
| 20-23    | GPIO_25..28          | GPIO_29..32           |
| 24       | GND                  | 3V3                   |

J3 (top edge, position 24 = USB side):

| Position | Inner row (odd pads) | Outer row (even pads) |
| -------- | -------------------- | --------------------- |
| 1        | GND                  | 3V3                   |
| 2-5      | GPIO_33..36          | GPIO_37..40           |
| 6        | GND                  | 3V3                   |
| 7-10     | GPIO_41..44          | GPIO_45..48           |
| 11       | GND                  | 3V3                   |
| 12-15    | GPIO_49..52          | GPIO_53..56           |
| 16       | GND                  | 3V3                   |
| 17-20    | GPIO_57..60          | GPIO_61..64           |
| 21       | GND                  | 3V3                   |
| 22       | PLL0_IN              | PLL1_IN               |
| 23       | 3V3                  | 3V3                   |
| 24       | 5V                   | 5V                    |

| Header                          | Pins                                                                           |
| ------------------------------- | ------------------------------------------------------------------------------ |
| J4 (right edge, pin 1 = bottom) | 1 = GND, 2 = CRESET_B, 3 = QSPI_CS_B, 4 = QSPI_SCK, 5 = QSPI_IO0, 6 = QSPI_IO1 |

The breakout board ([`breakout/`](breakout/)) accepts the Cherry via female
pin sockets (J2/J3/J4 plug straight in) and brings the 64 GPIOs out as eight
standard Pmod ports (8 GPIO each), plus an SPI header and a power/CRESET
utility header.

## BOM

| Ref   | Part                                     | Package         | Description              | Cost  | Buy                                                                                           |
| ----- | ---------------------------------------- | --------------- | ------------------------ | ----- | --------------------------------------------------------------------------------------------- |
| U1    | [W25Q32JVSSIQ](../../parts/W25Q32JV.pdf) | SOIC-8 208mil   | 32Mbit SPI Flash         | -     | [digikey](https://www.digikey.com/en/products/result?keywords=W25Q32JVSSIQ)                   |
| U2    | [iCE40HX8K-BG121](../../parts/iCE40.pdf) | caBGA-121 0.8mm | FPGA 7680 LUTs           | -     | [digikey](https://www.digikey.com/en/products/result?keywords=ICE40HX8K-BG121)                |
| U3-U4 | [TPS62A02](../../parts/TPS62A02.pdf)     | SOT-23-6        | 2A DC-DC Converter       | $0.25 | [digikey](https://www.digikey.jp/ja/products/detail/texas-instruments/TPS62A02PDDCR/22147220) |
| D1    | USBLC6-2SC6                              | SOT-23-6        | USB ESD protection       | -     | [digikey](https://www.digikey.jp/ja/products/result?keywords=USBLC6-2SC6)                     |
| X1    | OXETDLJANF-48.000000MHz                  | 3.2x2.5mm       | 48MHz XO                 | -     | generic                                                                                       |
| FB1   | GZ2012D601TF                             | 0805            | Ferrite bead (USB VBUS)  | -     | [lcsc](https://www.lcsc.com/search?q=GZ2012D601TF)                                            |
| J1    | USB4085-GF-A                             | SMD 16pin       | USB-C connector          | $1.01 | [digikey](https://www.digikey.jp/ja/products/detail/gct/USB4085-GF-A/9859662)                 |
| J2-J3 | Pin header 2x24                          | 2.54mm Pitch    | GPIO                     | -     | generic                                                                                       |
| J4    | Pin header 1x06                          | 2.54mm Pitch    | External SPI programming | -     | generic                                                                                       |
### Passives

| Ref                       | Value                | Pkg  | Qty |
| ------------------------- | -------------------- | ---- | --- |
| C1,C3,C5,C14,C17          | 10uF                 | 0805 | 5   |
| C4,C6                     | 22uF                 | 0805 | 2   |
| C2,C7-C13,C15-C16,C18-C24 | 100nF               | 0402 | 17  |
| L1-L2                     | TFM201208ALD-1R0MTCA | 0805 | 2   |
| R1-R2                     | 5.1k                 | 0402 | 2   |
| R3,R5-R6                  | 100k                 | 0402 | 3   |
| R4                        | 22k                  | 0402 | 1   |
| R7                        | 1.5k                 | 0402 | 1   |
| R8-R9                     | 68                   | 0402 | 2   |
| R10-R13,R16-R17,R22-R23   | 10k                  | 0402 | 8   |
| R14,R18-R21,R24-R25       | 1k                   | 0402 | 7   |
| R15                       | 100                  | 0402 | 1   |
| D2-D4,D6-D7               | KT-0603R             | 0603 | 5   |
| D5                        | LED_AMBER_0603       | 0603 | 1   |
| SW1-SW2                   | TS-1187A-B-A-B       | SMD  | 2   |
| JP1-JP2                   | Solder jumper        | SMD  | 2   |

## Build

Toolchain: [Yosys](https://github.com/YosysHQ/yosys) + [nextpnr-ice40](https://github.com/YosysHQ/nextpnr) + [icestorm](https://github.com/YosysHQ/icestorm)

The pin and timing constraint files are
[`firmware/cherry.pcf`](firmware/cherry.pcf) and
[`firmware/cherry.sdc`](firmware/cherry.sdc). Yosys produces the JSON netlist
and nextpnr consumes the PCF/SDC:

```bash
mkdir -p build
yosys -p 'synth_ice40 -top top -json build/top.json' rtl/top.v
nextpnr-ice40 --hx8k --package bg121 --freq 48 \
  --json build/top.json --pcf firmware/cherry.pcf --sdc firmware/cherry.sdc \
  --asc build/top.asc
icepack build/top.asc build/top.bin
```

Only ports present in the top-level HDL need to be used; nextpnr reports the
other PCF entries as harmless `unmatched constraint` warnings. Keep `clk_48m`
as an input. The commented SPI-flash constraints are intentionally reserved
because the flash and FPGA configuration controller share those four nets.

For recovery programming, power the board from USB and connect a 3.3V SPI
programmer to J4. Hold `CRESET_B` low while accessing the W25Q32, then release
it to boot the newly written image.
