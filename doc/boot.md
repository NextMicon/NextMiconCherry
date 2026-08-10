# Boot Sequence

[日本語](boot.ja.md)

Wire protocol: [CDC Flash Protocol](flash.md)

This document defines the intended Cherry boot behavior for the hardware, FPGA
images, and host tool. It does not imply that every transport and manifest
check is already implemented. The flash layout below remains subject to final
bitstream size and `icemulti` verification.

## Images and cold-boot selection

The W25Q32 stores four independently selectable FPGA images. The two solder
jumpers form `CBSEL1:CBSEL0`; an open jumper is `0`, and a solder bridge is `1`.
Changing a jumper does not affect the running image. The new value is sampled
only at the next rail reset.

| Jumper value | Image | Role | Framed channels |
| --- | ---: | --- | --- |
| `00` | 0 | Protected bootloader, programmer, and recovery image | BOOT and FLASH |
| `01` | 1 | Default production application | BOOT and UART |
| `10` | 2 | Alternate user application | BOOT and UART |
| `11` | 3 | Alternate application or diagnostics | BOOT and UART |

Both jumpers are normally left open during development. Production boards
normally bridge bit 0 so that image 1 starts without a host.

## Cold boot

1. USB VBUS powers the board. Releasing `RESET` enables the 3.3 V and 1.2 V
   regulators and lets both rails start from a discharged state.
2. The iCE40 configuration controller reads the cold-boot applet and vector
   table at flash address `0x000000`.
3. The controller samples `CBSEL1:CBSEL0` and reads the selected image address
   from the vector table.
4. Value `00` loads image 0. Values `01`, `10`, and `11` load images 1, 2, and 3
   directly; image 0 is not executed first.
5. After a valid configuration has loaded, the open-drain `CDONE` pin releases
   high through its pull-up.
6. The selected image initializes its 48 MHz USB logic and asserts the
   controllable D+ pull-up. Every image enumerates with the same CDC ACM
   identity and endpoint layout.

Image 0 turns on the amber `PROG` LED and waits indefinitely for a host command.
It never times out into a user image. Images 1-3 keep `PROG` off and provide the
common BOOT manager plus the framed UART byte-stream channel.

## USB transport relevant to boot

Every image exposes one CDC ACM serial function: EP1 IN carries CDC
notifications and EP2 OUT/IN carries the framed byte stream. Frames contain a
channel number, so BOOT, FLASH, and UART never inspect one another's payload.

| Channel | Image 0 | Images 1-3 |
| --- | --- | --- |
| BOOT (`0x01`) | Available | Available |
| FLASH (`0x02`) | Available | Unavailable |
| UART (`0x03`) | Unavailable | Available |

GET_INFO reports the active image and capabilities in-band. USB descriptors,
VID/PID, product string, and serial number remain the same across all images.

## Host-requested warm boot

Every valid image implements the common BOOT service. A warm boot selects the
same four vector-table entries as a cold boot, but uses internal `S1:S0` inputs
to `SB_WARMBOOT`; it does not resample the external solder jumpers.

1. The host sends a framed BOOT SELECT_IMAGE command containing one target
   image byte, `0` through `3`, through the CDC stream.
2. The active image validates the image number and destination manifest. The
   framed response contains one status byte:

   | Status | Meaning |
   | ---: | --- |
   | `0` | Request accepted |
   | `1` | Invalid image number |
   | `2` | Invalid destination manifest |
   | `3` | Manager busy |

3. For an accepted request, the complete response frame and CDC IN transfer
   finish before USB or QSPI is quiesced. The host therefore receives an
   explicit acknowledgement rather than relying on the later USB disconnect.
4. The manager blocks new QSPI work, waits for the current operation to finish
   and for the flash WIP bit to clear, restores ordinary one-bit SPI command
   mode, and raises flash `/CS`.
5. The manager disconnects USB, registers the target on `S1:S0`, and asserts
   `SB_WARMBOOT` on a later clock. `BOOT` remains asserted until
   reconfiguration removes the current logic.
6. The configuration controller loads the selected vector, and the new image
   reconnects and enumerates again with the same USB identity.

Selecting the currently active image deliberately restarts it. Warm boot does
not change the physical jumpers, so the next `RESET` performs a cold boot using
the jumper value again. USB disconnect and re-enumeration are intentional;
there is no USB block that remains resident across configurations.

## Development programming loop

1. Open both jumpers (`00`) and press `RESET`. Image 0 starts, enumerates as the
   bootloader, and remains available indefinitely.
2. Through the image-0 FLASH channel, erase only the selected image 1, 2, or 3
   slot, then write its bitstream and manifest.
3. Verify the manifest, CRC, and/or flash readback before requesting a boot.
4. Send framed BOOT SELECT_IMAGE `n`. After the accepted response, image 0
   warm-boots image `n` and the host waits for the same CDC device to reappear.
5. To program again, send SELECT_IMAGE 0 through the user image's BOOT channel
   and wait for GET_INFO to report image 0.

A host may also switch directly between valid user images with `BOOT 1`,
`BOOT 2`, or `BOOT 3` when no flash write is required.

## Flash layout

The current plan divides the 4 MiB W25Q32 into four 256 KiB image regions and a
3 MiB user-data region. These addresses match the current protocol constants,
but remain proposed until the final bitstreams and multiboot image are checked.

| Flash range | Size | Contents | Write policy |
| --- | ---: | --- | --- |
| `0x000000-0x03FFFF` | 256 KiB | Cold-boot table and protected image 0 | Factory/recovery tool only |
| `0x040000-0x07FFFF` | 256 KiB | Image 1 | Image 0 programmer only |
| `0x080000-0x0BFFFF` | 256 KiB | Image 2 | Image 0 programmer only |
| `0x0C0000-0x0FFFFF` | 256 KiB | Image 3 | Image 0 programmer only |
| `0x100000-0x3FFFFF` | 3 MiB | User data | Explicit user-data operations only |

The factory image is assembled at 256 KiB alignment:

```bash
icemulti -c -a18 -o factory.bin image0.bin image1.bin image2.bin image3.bin
```

Normal USB programming must never erase or program image 0. User code must not
leave the W25Q32 in persistent QPI mode, because the next cold boot requires
ordinary SPI command framing.

## RESET, external programming, and recovery

The front-panel `RESET` button is a rail reset, not a direct `CRESET_B` reset.
While held, it disables both regulators through `PWR_EN`; releasing it restarts
the rails and causes the cold-boot selection to be sampled again. Supplying the
3.3 V rail externally can bypass this behavior and is not a supported normal
operating mode.

`CRESET_B` remains pulled high and is exposed on the external SPI header J5 for
factory programming and last-resort recovery:

1. Power the board from USB and connect a 3.3 V SPI programmer to J5.
2. Pull `CRESET_B` low so that the shared configuration pins are high
   impedance.
3. Program and verify the complete factory multiboot image through
   CS/SCK/MOSI/MISO.
4. Release `CRESET_B`; the FPGA reads the cold-boot table and follows the normal
   jumper-selected cold-boot sequence.

If a user image is invalid or cannot process `BOOT 0`, open both jumpers and
press `RESET` to start the protected image 0. If image 0 or the cold-boot table
is damaged, use the external SPI procedure above. A factory image should
contain a valid default image 1 and safe manager-capable placeholder images in
unused slots so that every selectable vector remains recoverable.

## Boot-time hardware constraints

- Do not externally drive the shared configuration pins K10 (`/CS`), L10
  (`SCK`), K9 (`IO0`), or J9 (`IO1`) during cold boot.
- After configuration, the active image owns all six QSPI signals. Before a
  warm boot it must quiesce the interface as described above.
- FPGA ball E10 is driven by the board's 48 MHz oscillator and must remain an
  HDL clock input.
