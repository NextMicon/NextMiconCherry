# NextMiconCherry

FPGA Board for Beginners

## Schematic

![](doc/img/diagram.dio.svg)

## Specs

- FPGA: Lattice iCE40LP8K (7680 LUTs, BGA-81)
- USB: FT2232HL (Channel A: SPI programming, Channel B: UART)
- Flash: W25Q32 (32Mbit SPI, auto-boot)
- Power: USB 5V -> 3.3V (AMS1117) -> 1.2V (AP2112K)
- GPIO: 2x20 pin header (3.3V logic)
- Board: 50mm x 35mm, 2-layer FR4

## BOM

| Ref | Part                            | Package   | Description          | Cost   | Buy                                              |
| --- | ------------------------------- | --------- | -------------------- | ------ | ------------------------------------------------ |
| U2  | [iCE40LP8K-CM81](doc/iCE40.pdf) | BGA-81    | FPGA 7680 LUTs       | $11.55 | [digikey](https://www.digikey.jp/short/tc7d9m3n) |
| U1  | [FT2232HL](doc/FT2232H.pdf)     | LQFP-64   | Dual USB-UART/SPI    | $8.51  | [digikey](https://www.digikey.jp/short/h3wjqdqr) |
| U3  | W25Q32JVSSIQ                    | SOIC-8    | 32Mbit SPI Flash     | $0.96  | [digikey](https://www.digikey.jp/short/p5wz9rfn) |
| U4  | AMS1117-3.3                     | SOT-223   | 3.3V LDO 1A          | $0.30  | [digikey](https://www.digikey.jp/short/bvj2wqzn) |
| U5  | AP2112K-1.2TRG1                 | SOT-23-5  | 1.2V LDO 600mA       | $0.35  | [digikey](https://www.digikey.jp/short/4r5t2jht) |
| Y1  | ABM8-12.000MHZ-B2-T             | 3.2x1.5mm | 12MHz Crystal (18pF) | $0.30  |                                                  |
| J1  | USB Type-C Receptacle           | SMD 16pin | USB-C connector      | $0.80  |                                                  |
| J2  | Pin Header 2x20                 | 2.54mm    | GPIO header          | $0.50  |                                                  |
| FB1 | Ferrite Bead 600R@100MHz        | 0805      | USB power filter     | $0.05  |                                                  |

### Passives

| Ref     | Value | Package | Qty | Cost   | Notes                |
| ------- | ----- | ------- | --- | ------ | -------------------- |
| C1-C8   | 100nF | 0402    | 8   | $0.16  | IC decoupling        |
| C9-C12  | 10uF  | 0805    | 4   | $0.20  | LDO in/out bulk      |
| C13-C14 | 18pF  | 0402    | 2   | $0.04  | Crystal load caps    |
| C15     | 4.7uF | 0603    | 1   | $0.03  | FT2232H VCCORE       |
| R1-R2   | 5.1K  | 0402    | 2   | $0.02  | USB-C CC pull-down   |
| R3      | 12K   | 0402    | 1   | $0.01  | FT2232H REF resistor |
| R4      | 10K   | 0402    | 1   | $0.01  | CRESET_B pull-up     |
| R5-R8   | 1K    | 0402    | 4   | $0.04  | LED current limiting |
| D1-D4   | LED   | 0603    | 4   | $0.20  | PWR/CDONE/USER x2    |
| SW1-SW2 | Tact  | 3x6mm   | 2   | $0.20  | Reset/User button    |

## Net Connections

```
FT2232H Channel A (MPSSE/SPI) -> FPGA Programming:
  ADBUS0 (SCK)  -> iCE40 SPI_SCK  + Flash CLK
  ADBUS1 (MOSI) -> iCE40 SPI_SI   + Flash DI
  ADBUS2 (MISO) -> iCE40 SPI_SO   + Flash DO
  ADBUS3 (CS)   -> Flash ~CS
  ADBUS4        -> iCE40 CRESET_B
  ADBUS5        -> iCE40 CDONE
  ADBUS6        -> iCE40 SPI_SS

FT2232H Channel B (UART) -> User Communication:
  BDBUS0 (TX)   -> iCE40 IOB_41
  BDBUS1 (RX)   -> iCE40 IOB_42

Clock:
  12MHz Crystal -> FT2232H OSCI/OSCO
  ACBUS0 (CLKOUT) -> iCE40 GBIN0

Power:
  USB 5V -> FB1 -> AMS1117-3.3 -> 3.3V -> AP2112K-1.2 -> 1.2V
  3.3V: FT2232H, iCE40 VCCIO, Flash, GPIO
  1.2V: iCE40 VCC (core)
```

## Build

Toolchain: [Yosys](https://github.com/YosysHQ/yosys) + [nextpnr-ice40](https://github.com/YosysHQ/nextpnr) + [icestorm](https://github.com/YosysHQ/icestorm)

Programming: [iceprog](https://github.com/YosysHQ/icestorm) via FT2232H Channel A (MPSSE SPI)
