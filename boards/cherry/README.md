# 🍒 NextMicon Cherry 🍒

FPGA Board for Beginners

## Repository layout

- [`board`](board/): KiCad design and fabrication outputs
- [`breakout`](breakout/): pogo-pin breakout and factory-test fixture
- [`firmware`](firmware/): FPGA HDL and constraints

## Schematic

![](cherry.png)

![](../../doc/img/diagram.dio.svg)

## Specs

- FPGA: Lattice iCE40HX8K-BG121 (7680 LUTs, 9x9mm, 0.8mm pitch)
- GPIO: 36 pins (3.3V logic), 2x24 PinHeader x2 (paired contacts)
- Clock: 48MHz
- Flash: 32Mbit SPI Flash (3.5 MiB user-data area)
- Power: USB 5V → 3.3V → 1.2V
- Signal: 3.3V
- USB ESD Protection
- Switch: RESET / USER buttons, boot/user solder-jumper selector
- LED: PWR / USER0 / USER1 / PROG
- Board: 61mm x 31mm, 4-layer FR4

## Pinout

| Header                             | Pins                                                                           |
| ---------------------------------- | ------------------------------------------------------------------------------ |
| J2 (bottom rows, pin 1 = USB side) | 1 = 5V, 2 = 3V3, 3-5 = GND, 6 = CRESET_B, 7-24 = GPIO_1..18                    |
| J3 (top rows, pin 24 = USB side)   | 24 = 5V, 23 = 3V3, 22-19 = GND, 1-18 = GPIO_19..36                             |
| J4 (right edge, pin 1 = bottom)    | 1 = GND, 2 = CRESET_B, 3 = QSPI_CS_B, 4 = QSPI_SCK, 5 = QSPI_IO0, 6 = QSPI_IO1 |

J2 and J3 have two contacts for every pin number; the inner and outer contacts at the same position are electrically common.

## BOM

| Ref   | Part                                     | Package         | Description              | Cost  | Buy                                                                                            |
| ----- | ---------------------------------------- | --------------- | ------------------------ | ----- | ---------------------------------------------------------------------------------------------- |
| U1    | [W25Q32JVSSIM](../../parts/W25Q32JV.pdf) | SOIC-8 208mil   | 32Mbit SPI Flash         | -     | [digikey](https://www.digikey.com/en/products/result?keywords=W25Q32JVSSIM)                    |
| U2    | [iCE40HX8K-BG121](../../parts/iCE40.pdf) | caBGA-121 0.8mm | FPGA 7680 LUTs           | -     | [digikey](https://www.digikey.com/en/products/result?keywords=ICE40HX8K-BG121)                 |
| U3-U4 | [TPS62A02](../../parts/TPS62A02.pdf)     | SOT-23-6        | 2A DC-DC Converter       | $0.25 | [digikey](https://www.digikey.jp/ja/products/detail/texas-instruments/TPS62A02PDDCR/22147220)  |
| D1    | USBLC6-2SC6                              | SOT-23-6        | USB ESD protection       | -     | [digikey](https://www.digikey.jp/ja/products/result?keywords=USBLC6-2SC6)                      |
| X1    | OXETDLJANF-48.000000MHz                  | 3.2x2.5mm       | 48MHz XO                 | -     | generic                                                                                        |
| FB1   | BLM21AG601SH1D                           | 0805            | Ferrite bead (USB VBUS)  | $0.19 | [digikey](https://www.digikey.jp/ja/products/detail/murata-electronics/BLM21AG601SH1D/2588067) |
| J1    | USB4085-GF-A                             | SMD 16pin       | USB-C connector          | $1.01 | [digikey](https://www.digikey.jp/ja/products/detail/gct/USB4085-GF-A/9859662)                  |
| J2-J3 | Pin header 2x24, paired contacts         | 2.54mm Pitch    | GPIO                     | -     | generic                                                                                        |
| J4    | Pin header 1x06                          | 2.54mm Pitch    | External SPI programming | -     | generic                                                                                        |
### Passives

| Ref                       | Value                | Pkg  | Qty |
| ------------------------- | -------------------- | ---- | --- |
| C1,C3,C5,C14,C17          | 10uF                 | 0805 | 5   |
| C4,C6                     | 22uF                 | 0805 | 2   |
| C2,C7-C13,C15-C16,C18-C23 | 100nF                | 0402 | 16  |
| L1-L2                     | TFM201208ALD-1R0MTCA | 0805 | 2   |
| FB1                       | GZ2012D601TF         | 0805 | 1   |
| R1                        | 100                  | 0402 | 1   |
| R2-R5,R15-R16,R22-R23     | 10k                  | 0402 | 8   |
| R6,R18-R21,R24            | 1k                   | 0402 | 6   |
| R7-R8                     | 68                   | 0402 | 2   |
| R9                        | 1.5k                 | 0402 | 1   |
| R10-R11                   | 5.1k                 | 0402 | 2   |
| R12,R14,R17               | 100k                 | 0402 | 3   |
| R13                       | 22k                  | 0402 | 1   |
| D2-D4                     | KT-0603R             | 0603 | 3   |
| D5                        | LED_AMBER_0603       | 0603 | 1   |
| SW1                       | TS-1187A-B-A-B       | SMD  | 1   |
| SW2                       | USER                 | SMD  | 1   |
| JP1                       | USER                 | SMD  | 1   |

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
