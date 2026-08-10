# Boot Sequence

## Power-on / autonomous boot

1. USB VBUS starts the 3.3V and 1.2V regulators.
2. `CRESET_B` is held high by its pull-up; SW1 power-cycles both FPGA rails.
3. With `CRESET_B` high, the iCE40 reads the W25Q32 over `QSPI_CS_B`,
   `QSPI_SCK`, `QSPI_IO0` and `QSPI_IO1`.
4. After a valid image is loaded, the open-drain `CDONE` pin releases high via
   R12. `CDONE` remains available as a status signal but has no indicator LED.

## Programming through the external SPI header

1. Power the board from USB and connect a 3.3V SPI programmer to J5.
2. Assert `CRESET_B` through J5 so the FPGA configuration pins are high
   impedance.
3. Program and verify the flash through CS/SCK/MOSI/MISO.
4. Release `CRESET_B`; the iCE40 wakes the flash and performs its normal boot.

Do not drive the shared configuration pins K10/L10/K9/J9 during boot. FPGA
ball E10 is the input from the board's 48MHz oscillator and must remain an HDL
input.
