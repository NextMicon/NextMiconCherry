# NextMicon Cherry Driver App

Host-side programmer and image manager. The initial implementation contains
the endpoint/image contract shared with the HDL:

- EP1: BOOT in every image
- EP2: FLASH in image 0 only
- EP3: UART in images 1-3 only

USB transport and command-line handling are not implemented yet.

The EP1 BOOT request is one byte containing image number `0` through `3`.
EP1 IN returns one byte before reconfiguration: `0` accepted, `1` invalid
image, `2` invalid manifest, or `3` busy. On success the FPGA waits until that
response transfer has completed, quiesces USB/QSPI, and starts warm boot.

USB (Linux / Windows / Mac)

## CLI Usage

### SPI Flash Memmap

There are 4 bitstream slots and a user rom area

- 0: Flash Bitstream
- 1-3: User Bitstream
- 4: User ROM

### Cherry command

List-up connected boards

```
$ cherry ls
cherry-0123
cherry-4567
```

Select Bitstream and boot

```
$ cherry boot <board>/<0-3>
```

Select slot and flash

```
$ cherry flash <board>/<1-3> <image>
```

**Dangerously update firmware**

You need Device ID (32Byte ASCII)
This ID is written on ship, and labbeled on package.
If you forgot ID, you can use any ID but hard to get support.

```
$ ID=0123 curl (https://..imggen.sh) | sh
$ cherry flash <board>/0 cherry-0.0.0-0123.bin
```
