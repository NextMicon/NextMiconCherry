# Boot Sequence

[日本語](boot.ja.md)

Wire protocol: [CDC Flash Protocol](flash.md)

This document defines the intended Cherry boot behavior for the hardware, FPGA
images, and host tool. It does not imply that every transport and manifest
check is already implemented. The flash layout remains subject to final
bitstream-size and `icemulti` verification.

## Images and cold-boot selection

The W25Q32 stores two FPGA images with fixed roles:

| `CBSEL0` | Role | Contents | Framed channels |
| ---: | --- | --- | --- |
| `0` | `boot` | Protected programmer and recovery image | BOOT and FLASH |
| `1` | `user` | User application | BOOT and UART |

The board has one `CBSEL0` solder jumper. Open selects `boot`; bridging it
selects `user`. `CBSEL1` is permanently held low, so cold boot cannot select
the unused iCE40 vectors 2 and 3. Changing the jumper does not affect the
running image; the new value is sampled at the next rail reset.

## Cold boot

1. USB VBUS powers the board. Releasing `RESET` enables the 3.3 V and 1.2 V
   regulators and lets both rails start from a discharged state.
2. The iCE40 configuration controller reads the cold-boot applet and vector
   table at flash address `0x000000`.
3. The controller samples `CBSEL0`. An open jumper loads `boot`; a bridge loads
   `user` directly. The boot image does not run first when `user` is selected.
4. After a valid configuration has loaded, the open-drain `CDONE` pin releases
   high through its pull-up.
5. The selected image initializes its 48 MHz USB logic and asserts the
   controllable D+ pull-up. Both images enumerate with the same CDC ACM
   identity and endpoint layout.

`boot` turns on the amber `PROG` LED and waits indefinitely for a host command.
It never times out into `user`. The `user` image keeps `PROG` off and provides
the common BOOT manager plus the framed UART byte-stream channel.

## USB transport relevant to boot

Both images expose one CDC ACM serial function. EP1 IN carries CDC
notifications and EP2 OUT/IN carries the framed byte stream. Frames contain a
channel number, so BOOT, FLASH, and UART never inspect one another's payload.

| Channel | `boot` | `user` |
| --- | --- | --- |
| BOOT (`0x01`) | Available | Available |
| FLASH (`0x02`) | Available | Unavailable |
| UART (`0x03`) | Unavailable | Available |

GET_INFO reports the active role and capabilities in-band. USB descriptors,
VID/PID, product string, and serial number remain the same in both images.

## Host-requested warm boot

Both valid images implement the BOOT service. A warm boot uses internal
`S1:S0` inputs to `SB_WARMBOOT`; it does not resample the solder jumper. `S1`
is always `0`, and `S0` selects `boot` (`0`) or `user` (`1`).

1. The host sends a framed BOOT SELECT_IMAGE command containing one target
   byte: `0` for `boot` or `1` for `user`.
2. The active image validates the role and, for `user`, its manifest. The
   response contains one status byte:

   | Status | Meaning |
   | ---: | --- |
   | `0` | Request accepted |
   | `1` | Invalid image byte or payload |
   | `2` | Invalid user manifest |
   | `3` | Manager busy |

3. For an accepted request, the response frame and CDC IN transfer finish
   before USB or QSPI is quiesced.
4. The manager blocks new QSPI work, waits for current work and the flash WIP
   bit to clear, restores ordinary one-bit SPI command mode, and raises flash
   `/CS`.
5. The manager disconnects USB, registers the target on `S0` while holding
   `S1=0`, and asserts `SB_WARMBOOT` on a later clock.
6. The selected image loads and enumerates again with the same USB identity.

Selecting the active role deliberately restarts it. Warm boot does not change
the physical jumper, so the next `RESET` again uses the jumper value.

## Development programming loop

1. Open the selector jumper and press `RESET` to start `boot`.
2. Through its FLASH channel, erase the single `user` slot and write the
   bitstream and manifest.
3. Verify the manifest, CRC, and flash readback.
4. Send SELECT_IMAGE `1`; after acknowledgement, wait for `user` to enumerate.
5. To program again, send SELECT_IMAGE `0` and wait for `boot` to enumerate.

The host tools therefore never ask for a destination slot: `user` is the only
USB-writable FPGA image.

## Flash layout

The 4 MiB W25Q32 contains two 256 KiB image regions and a 3.5 MiB user-data
region.

| Flash range | Size | Contents | Write policy |
| --- | ---: | --- | --- |
| `0x000000-0x03FFFF` | 256 KiB | Cold-boot table and protected `boot` image | Factory/recovery tool only |
| `0x040000-0x07FFFF` | 256 KiB | `user` image and manifest | `boot` programmer only |
| `0x080000-0x3FFFFF` | 3.5 MiB | User data | Explicit user-data operations only |

The factory image is assembled at 256 KiB alignment:

```bash
icemulti -c -a18 -o factory.bin boot.bin user.bin
```

Normal USB programming must never erase or program `boot`. User code must not
leave the W25Q32 in persistent QPI mode because cold boot requires ordinary SPI
command framing.

## RESET, external programming, and recovery

The front-panel `RESET` button is a rail reset, not a direct `CRESET_B` reset.
While held, it disables both regulators through `PWR_EN`; releasing it restarts
the rails and samples the selector again. Supplying 3.3 V externally can bypass
this behavior and is not a supported normal operating mode.

`CRESET_B` is pulled high and exposed on J5 for factory programming and
last-resort recovery:

1. Power the board from USB and connect a 3.3 V SPI programmer to J5.
2. Pull `CRESET_B` low so the shared configuration pins are high impedance.
3. Program and verify the complete factory image through CS/SCK/MOSI/MISO.
4. Release `CRESET_B`; the FPGA follows the normal jumper-selected cold boot.

If `user` is invalid or cannot process SELECT_IMAGE `0`, open the jumper and
press `RESET` to start protected `boot`. If `boot` or the cold-boot table is
damaged, use the external SPI procedure.

## Boot-time hardware constraints

- Do not externally drive K10 (`/CS`), L10 (`SCK`), K9 (`IO0`), or J9 (`IO1`)
  during cold boot.
- After configuration, the active image owns all six QSPI signals and must
  quiesce them before warm boot.
- FPGA ball E10 is driven by the 48 MHz oscillator and must remain an HDL clock
  input.
