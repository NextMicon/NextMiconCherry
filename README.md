# NextMicon FPGA

NextMicon is a family of open-source FPGA development boards. Choose the compact Cherry to get started, or Grape for a larger FPGA and more I/O.

|       | [🍒 Cherry](boards/cherry/) | [🍇 Grape](boards/grape/)     | [🍈 Melon](boards/melon/)      |
| ----- | -------------------------- | ---------------------------- | ----------------------------- |
| FPGA  | Lattice iCE40HX8K-BG121    | AMD Spartan-7 XC7S50-CSGA324 | AMD Artix-7 XC7A100T-1FGG676C |
| Logic | 7,680 (4-input LUT)        | 32,600 (6-input LUT)         | 63,400 (6-input LUT)          |
| BRAM  | 128 Kbit                   | 2,700 Kbit                   | 4,860 Kbit                    |
| DSP   | —                          | 120                          | 240                           |
| GPIO  | 64                         | 128                          | 256                           |

## 🍒 NextMicon Cherry

![](boards/cherry/cherry.png)

**A compact board for learning and small projects.** Cherry is built around the Lattice iCE40HX8K-BG121, with 7,680 LUTs, 64 GPIO pins, native USB Full-Speed, and protected `boot` plus writable `user` FPGA images. The repository includes its KiCad PCB design, fabrication outputs, bootloader HDL, and host application.

[Explore Cherry →](boards/cherry/)

Cherry firmware can be managed with the [`nmb` CLI](flash/cli/README.md) or the
[Web Serial flasher](flash/web/README.md).

## 🍇 NextMicon Grape

![](boards/grape/grape.png)

**A mid-range board for multi-channel phased-array acoustic field generation.** Grape uses the AMD Spartan-7 XC7S50-CSGA324 with 128 GPIO outputs and a 128-Mbit QSPI flash. Firmware is built and programmed with a fully open-source Yosys, nextpnr-xilinx, Project X-Ray, and openFPGALoader stack. Its schematic and PCB are being migrated from the earlier Artix-7 prototype.

[Explore Grape →](boards/grape/)
