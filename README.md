# 🍒 NextMiconCherry

FPGA Board for Beginners

## Schematic

![](doc/img/diagram.dio.svg)

## Specs

- FPGA: Lattice iCE40LP8K (7680 LUTs, BGA-81)
- USB: FT2232HL (Channel A: SPI programming, Channel B: UART)
- Flash: W25Q32 (32Mbit SPI, auto-boot)
- Power: USB 5V -> 3.3V (AMS1117) -> 1.2V (AP2112K)
- GPIO: 2x20 castellated + through-hole pins, 2.54mm pitch (3.3V logic)
- Board: 51mm x 21mm (Raspberry Pi Pico compatible footprint), 2-layer FR4

## BOM

| Ref   | Part                              | Package   | Description          | Cost   | Buy                                                                                       |
| ----- | --------------------------------- | --------- | -------------------- | ------ | ----------------------------------------------------------------------------------------- |
| U2    | [iCE40LP8K-CM81](data/iCE40.pdf)  | BGA-81    | FPGA 7680 LUTs       | $11.55 | [digikey](https://www.digikey.jp/short/tc7d9m3n)                                          |
| U1    | [FT2232HL](data/FT2232H.pdf)      | LQFP-64   | Dual USB-UART/SPI    | $8.51  | [digikey](https://www.digikey.jp/short/h3wjqdqr)                                          |
| U3    | [MX25L3233F](data/MX25L3233F.pdf) | SOP-8     | 32Mbit SPI Flash     | $1.28  | [digikey](https://www.digikey.jp/ja/products/detail/macronix/MX25L3233FM2I-08G/7402341)   |
| U4-U5 | [TPS62A02](data/TPS62A02.pdf)     | SOT-23-6  | DC-DC Converter      | $0.25  | [digikey](https://www.digikey.jp/ja/products/detail/texas-instruments/TPS62A02PDDCR/22147220) |
| Y1    | ABM8-12.000MHZ-B2-T               | 3.2x1.5mm | 12MHz Crystal (18pF) | $0.52  | [digikey](https://www.digikey.jp/ja/products/detail/abracon-llc/ABM8-12-000MHZ-B2-T/2001193) |
| J1    | USB4085-GF-A                      | SMD 16pin | USB-C connector      | $1.01  | [digikey](https://www.digikey.jp/ja/products/detail/gct/USB4085-GF-A/9859662)             |
| FB1   | BLM21AG601SH1D                    | 0805      | USB power filter     | $0.19  | [digikey](https://www.digikey.jp/ja/products/detail/murata-electronics/BLM21AG601SH1D/2588067) |

### Passives

| Ref     | Value | Package | Qty | Cost  | Notes                |
| ------- | ----- | ------- | --- | ----- | -------------------- |
| C1-C8   | 100nF | 0402    | 8   | $0.16 | IC decoupling        |
| C9-C12  | 10uF  | 0805    | 4   | $0.20 | LDO in/out bulk      |
| C13-C14 | 18pF  | 0402    | 2   | $0.04 | Crystal load caps    |
| C15     | 4.7uF | 0603    | 1   | $0.03 | FT2232H VCCORE       |
| R1-R2   | 5.1K  | 0402    | 2   | $0.02 | USB-C CC pull-down   |
| R3      | 12K   | 0402    | 1   | $0.01 | FT2232H REF resistor |
| R4      | 10K   | 0402    | 1   | $0.01 | CRESET_B pull-up     |
| R5-R8   | 1K    | 0402    | 4   | $0.04 | LED current limiting |
| D1-D4   | LED   | 0603    | 4   | $0.20 | PWR/CDONE/USER x2    |
| SW1-SW2 | Tact  | 3x6mm   | 2   | $0.20 | Reset/User button    |

## Build

Toolchain: [Yosys](https://github.com/YosysHQ/yosys) + [nextpnr-ice40](https://github.com/YosysHQ/nextpnr) + [icestorm](https://github.com/YosysHQ/icestorm)

Programming: [iceprog](https://github.com/YosysHQ/icestorm) via FT2232H Channel A (MPSSE SPI)
