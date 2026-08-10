# NextMicon FPGA

NextMicon is a family of open-source FPGA development boards. Choose the compact Cherry to get started, or Grape for a larger FPGA and more I/O.

| [🍒 NextMicon Cherry](boards/cherry/)            | [🍇 NextMicon Grape](boards/grape/)           |
| ----------------------------------------------- | -------------------------------------------- |
| [![](boards/cherry/cherry.png)](boards/cherry/) | [![](boards/grape/grape.png)](boards/grape/) |

## 🍒 NextMicon Cherry

**A compact board for learning and small projects.** Cherry is built around the Lattice iCE40HX8K-BG121, with 7,680 LUTs, 36 GPIO pins, native USB Full-Speed, and protected `boot` plus writable `user` FPGA images. The repository includes its KiCad PCB design, fabrication outputs, bootloader HDL, and host application.

[Explore Cherry →](boards/cherry/)

Cherry firmware can be managed with the [`nmb` CLI](flash/cli/README.md) or the
[Web Serial flasher](flash/web/README.md).

## 🍇 NextMicon Grape

**A larger board for more ambitious designs.** Grape brings the same native-USB and multi-image concepts to the AMD Artix-7 XC7A35T, with 56 GPIO signals and a 128-Mbit QSPI flash. Its schematic is available now; PCB layout is still in progress.

[Explore Grape →](boards/grape/)
