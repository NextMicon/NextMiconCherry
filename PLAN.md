# Native USB Bootloader Conversion Plan

Status: implementation started. The endpoint/image constants, endpoint policy,
host-side BOOT packet types, final warm-boot request controller, and native-USB
schematic conversion now exist. USB transport, flash programming, UART
transport, image manifests, top-level HDL integration, and PCB routing remain
pending. The converted schematic passes KiCad ERC with no violations, and the
PCB component placement has been synchronized to that schematic.

## Goal

Replace the FT2232H programmer/UART with a TinyFPGA BX-style native USB
bootloader implemented in the iCE40HX8K-BG121. The flash contains four independently
selectable FPGA images:

- Image 0 is the protected USB bootloader and SPI flash programmer.
- Images 1, 2, and 3 are replaceable user designs.
- A two-bit slide/DIP switch drives `CBSEL[1:0]` and selects the image used for
  a cold boot.
- Warm boot commands select images under host control without changing the
  physical switch.

Every image implements a common native-USB front end with three logical
services. Availability depends on the active image:

| USB service | Image 0  | Images 1-3 | Purpose                                         |
| ----------- | -------- | ---------- | ----------------------------------------------- |
| `BOOT`      | Enabled  | Enabled    | Warm-boot image 0, 1, 2, or 3                   |
| `FLASH`     | Enabled  | Disabled   | Erase/write/read/verify permitted flash regions |
| `UART`      | Disabled | Enabled    | USB serial byte stream to/from user HDL         |

```text
                            +-- BOOT  (all images)
USB full-speed front end ---+-- FLASH (image 0 only)
                            +-- UART  (images 1-3 only)
```

The three services use different USB endpoint numbers. USB IN and OUT
directions are separate endpoint addresses, so each logical service owns a
matched pair:

| Service | Host-to-FPGA | FPGA-to-host | Transfer type | Max packet |
| --- | --- | --- | --- | ---: |
| `BOOT` | EP1 OUT (`0x01`) | EP1 IN (`0x81`) | Bulk | 64 bytes |
| `FLASH` | EP2 OUT (`0x02`) | EP2 IN (`0x82`) | Bulk | 64 bytes |
| `UART` | EP3 OUT (`0x03`) | EP3 IN (`0x83`) | Bulk | 64 bytes |

EP0 remains reserved for standard enumeration and USB class/control requests.
Image 0 advertises EP1 and EP2 but not EP3. Images 1-3 advertise EP1 and EP3
but not EP2. Unsupported or non-advertised service accesses are stalled rather
than routed into another service.

EP3 is the UART payload pair. If native OS virtual-COM compatibility requires a
CDC ACM interrupt-notification endpoint, allocate a separate class-support IN
endpoint for that purpose; it is not a fourth application data service and must
not carry BOOT, FLASH, or UART payload.

EP1 OUT uses a deliberately small fixed packet: exactly one byte containing the
target image number `0` through `3`. EP1 IN returns exactly one status byte:
`0` accepted, `1` invalid image, `2` invalid manifest, or `3` busy. For an
accepted request, the response transfer completes before USB/QSPI quiescence
and `SB_WARMBOOT`; the subsequent USB disconnect is therefore not the only
acknowledgement visible to the host.

`FLASH` in this table means the USB-accessible flash-programming service. User
images may still contain an application QSPI controller for reads and user-data
access; they do not expose erase/write programming commands through USB.

The design must remain recoverable when the user image is missing or invalid.
No FTDI configuration EEPROM, SPI bus switch, or external USB/serial converter
will be fitted.

## User-visible state machine

The mode switch drives the iCE40 cold-boot selection pin and is sampled by the
hard configuration controller after every cold start. Changing the switch does
not alter the running configuration until `RESET` is pressed.

| Slide-switch value | Cold-boot image | Intended use                           | USB presented to the host                |
| ------------------ | --------------- | -------------------------------------- | ---------------------------------------- |
| `00`               | Image 0         | Development, programming, recovery     | Bootloader CDC/programming protocol      |
| `01`               | Image 1         | Default production application         | Common BOOT service plus USB UART stream |
| `10`               | Image 2         | Alternate user application             | Common BOOT service plus USB UART stream |
| `11`               | Image 3         | Alternate user application/diagnostics | Common BOOT service plus USB UART stream |

Boot sequence:

1. The 3.3 V and 1.2 V rails start and the FPGA reads the cold-boot applet at
   flash address 0.
2. The configuration controller samples `CBSEL1` and `CBSEL0` and reads the
   selected vector address from the applet.
3. `00` directly loads image 0. The bootloader configures the 48 MHz USB clock,
   asserts the USB D+ pull-up, turns on `PROG`, and waits indefinitely for a
   host command. It does not time out into a user image.
4. `01`, `10`, or `11` directly loads the corresponding user image without
   first executing the bootloader.
5. Every supported image contains the common BOOT service. Images 1-3 also
   contain the standard USB UART wrapper and own all six QSPI signals.

USB disconnect/re-enumeration across a mode transition is intentional. There
is no continuously resident USB block shared between the four images.
The normal development workflow leaves the switch at `00`. Host commands write
images 1-3 and select which one to run using `SB_WARMBOOT`. Production hardware
normally leaves the switch at `01`, so image 1 starts autonomously without a
USB host.

### Common BOOT service

`SB_WARMBOOT` selects the same four vector-table entries using internal `S1`
and `S0` signals. It does not sample the external CBSEL pins:

- Every image accepts `BOOT 0`, `BOOT 1`, `BOOT 2`, and `BOOT 3` and warm-boots
  the requested valid image. Selecting the currently active image deliberately
  restarts that image.
- Images 1-3 reject every FLASH command as unsupported. Programming is
  performed only by image 0.
- The physical switch is unchanged. The next rail RESET is a cold boot and
  selects an image from external `CBSEL[1:0]` again.

Before asserting `BOOT`, finish every flash operation, wait until WIP is clear,
raise flash chip select, and leave the flash in ordinary one-bit SPI command
mode. Register `S1:S0` first, then assert `BOOT` on a later clock and keep it
asserted until reconfiguration clears the current logic.

## Host-controlled development workflow

1. Leave the two-bit slide switch at `00` and press RESET once. Image 0 starts,
   enumerates as the bootloader, and remains available indefinitely. The USB
   host may also be connected later; image 0 never times out automatically.
2. The host selects destination image 1, 2, or 3, erases only that slot, writes
   the bitstream and manifest, and verifies its CRC/readback.
3. The host sends `BOOT n`. Image 0 disconnects USB and warm-boots the requested
   image using internal `S1:S0`.
4. The selected user image enumerates with its management interface and user
   data interface. Normal application traffic uses only the user interface.
5. To program again, the host sends `BOOT 0` over the management interface.
   The user manager quiesces QSPI and USB, then warm-boots image 0.
6. The host waits for the bootloader identity to reappear and repeats the
   program/verify/boot sequence. No physical switch or button operation is
   required during this loop.

The host may also send `BOOT 1/2/3` to any user image to switch applications
directly without entering image 0 when no flash write is required.

If a user image is invalid, omits the standard manager, or is otherwise unable
to process `BOOT 0`, recovery is always available by setting the switch to `00`
and pressing RESET. For production operation, set the switch to `01`; every
cold start then loads image 1 directly and does not require a USB host.

## Bitstream and data storage

All four configurations are stored in the existing 32-Mbit (4-MiB) W25Q32 flash.
Only the selected configuration is held in the FPGA SRAM at runtime.

Proposed logical map, subject to confirmation with `icemulti` and the final
bitstream sizes:

| Main flash range    |    Size | Purpose                                           | Write policy                       |
| ------------------- | ------: | ------------------------------------------------- | ---------------------------------- |
| `0x000000-0x03FFFF` | 256 KiB | Cold-boot table and image 0: protected bootloader | Factory/recovery tool only         |
| `0x040000-0x07FFFF` | 256 KiB | Image 1: default production application           | Image 0 programmer only            |
| `0x080000-0x0BFFFF` | 256 KiB | Image 2: alternate application                    | Image 0 programmer only            |
| `0x0C0000-0x0FFFFF` | 256 KiB | Image 3: alternate application/diagnostics        | Image 0 programmer only            |
| `0x100000-0x3FFFFF` |   3 MiB | User data                                         | Explicit user-data operations only |

The initial factory image is assembled with 256-KiB image alignment:

```bash
icemulti -c -a18 -o factory.bin image0.bin image1.bin image2.bin image3.bin
```

Board name, hardware revision, flash map, and serial number are stored in the
W25Q32 security-register pages, not in a separate EEPROM. Normal programming
must never erase or program image 0. Consider enabling bottom-region flash
protection after factory programming, provided recovery tooling can explicitly
unlock it.

The factory image must contain a valid image 1, such as a USB CDC hello-world or
LED example, so a new board gives a useful result with the switch at `01`.
Unused image 2 and 3 slots receive a small safe placeholder image with the USB
manager, rather than erased or malformed configuration data.

## Mode controls and indicators

### Two-bit cold-boot switch

- Retain a separate momentary `USER` button and add a two-section slide/DIP
  switch labelled `IMAGE`, with visible bit labels `1` and `0`.
- Connect bit 0 to dedicated cold-boot pin `CBSEL0`, FPGA ball G5.
- Connect bit 1 to dedicated cold-boot pin `CBSEL1`, FPGA ball H5.
- Give both pins 10 kOhm pull-downs so both switches open defaults safely to
  image 0. Each closed switch connects its bit to 3.3 V through a small series
  resistor, making the marked ON state equal to binary 1 while limiting current
  if a future bitstream accidentally configures a CBSEL pin as an output.
- Generate the combined flash image with cold boot enabled (`icemulti -c`).
- After configuration, G5 and H5 become ordinary PIO, but both remain reserved
  board signals and are not published as expansion GPIO.

### RESET button

`RESET` performs a real board-rail reset while USB VBUS remains connected:

- Join the enable inputs of both TPS62A02 regulators as `PWR_EN`.
- Pull `PWR_EN` up to VBUS and pull it low with the reset button.
- While the button is held, both 3.3 V and 1.2 V are disabled. The regulators'
  active output discharge removes the residual rail charge.
- Releasing the button restarts both rails. The iCE40 configuration controller
  samples both slide switches through `CBSEL[1:0]` and directly loads the
  selected image.
- Add an RC delay/debounce footprint on `PWR_EN`; choose final values after
  measuring the rail discharge and startup waveforms.

This behavior assumes the board is powered from USB/VBUS. Supplying the 3.3 V
rail externally would bypass the rail-reset function and is outside the normal
supported use case. Keep `CRESET_B` pulled up and expose it on the right-edge
SPI programming header, even though the front-panel reset button no longer
drives it directly.

### Bootloader LED

Add a dedicated amber LED labelled `PROG`:

- Use FPGA ball J10, released by the package migration, as
  `prog_active`.
- Drive the LED from the bootloader, rather than directly from the mode switch,
  so it reports the configuration that is actually active rather than the
  selection for the next reset.
- `PROG` is on continuously while image 0 is accepting programmer commands.
- It is off during reset and in the user image. The standard user wrapper drives
  the pin low; an arbitrary image that leaves the pin unused also leaves the
  LED off.
- Retain the existing `PWR` and `CFG/CDONE` indicators. `PWR + CFG` on and
  `PROG` off means one of images 1-3 is active.
- Start with a 1 kOhm series resistor and verify brightness/current before BOM
  release.

## Native USB hardware

Follow the TinyFPGA BX full-speed USB connection closely:

| Function            | FPGA ball | Current Cherry use | Planned connection                           |
| ------------------- | --------- | ------------------ | -------------------------------------------- |
| USB D+              | B4        | `GPIO_28`          | Connector/ESD through 68 Ohm series resistor |
| USB D-              | A4        | `GPIO_27`          | Connector/ESD through 68 Ohm series resistor |
| USB pull-up control | A3        | `GPIO_31`          | 1.5 kOhm to D+                               |
| Clock               | E10       | 48 MHz oscillator  | Direct global-clock input                     |

- Retain the USB-C connector, both 5.1 kOhm CC pull-downs, and the low-capacitance
  USB ESD protector.
- Route D+/D- as a short 90 Ohm differential pair, keep the pair on one layer,
  and avoid stubs/test pads on the pair.
- The interface is USB 2.0 Full Speed (12 Mbit/s), not a high-speed USB PHY.
- Use a controllable D+ pull-up so rail reset and configuration changes cause a
  clean USB disconnect before the selected image enumerates.

Change the oscillator from 12 MHz to 48 MHz unless measurement or place-and-route
shows a reason not to. The iCE40HX8K-BG121 has two PLLs; a direct 48 MHz clock lets
the standard user-image USB wrapper operate without consuming either PLL. User
designs may divide 48 MHz or use the PLL for their own clock generation.

## QSPI flash wiring

The bootloader writes with ordinary single-bit SPI. Images 1-3 may use Quad SPI
for reads and user-data access.

| Flash signal | FPGA ball | Notes                                                        |
| ------------ | --------- | ------------------------------------------------------------ |
| `/CS`        | K10       | Configuration pin, user PIO after configuration              |
| `SCK`        | L10       | Configuration pin, user PIO after configuration              |
| `IO0`        | K9        | Configuration output, bidirectional in user images           |
| `IO1`        | J9        | Configuration input, bidirectional in user images            |
| `IO2/WP#`    | K6        | User PIO with a 10 kOhm pull-up                               |
| `IO3/HOLD#`  | J8        | User PIO with a 10 kOhm pull-up                               |

Do not enter persistent QPI command mode. Use Quad Output/Quad I/O read commands
while retaining ordinary one-bit SPI command framing, so the next cold boot can
always read the flash. User libraries must restrict erase/program operations to
the documented user-data range.

With the FT2232H removed, the FPGA is the only active master and no SPI bus
switch or contention resistors are needed.

## Factory programming and recovery

An empty flash cannot provide the native USB programmer. Add unpopulated pads
or a compact keyed header for an external fixture:

- `3V3`
- `GND`
- `CRESET_B`
- `CDONE`
- Flash `/CS`
- Flash `SCK`
- Flash `IO0/MOSI`
- Flash `IO1/MISO`

The fixture holds `CRESET_B` low, writes the complete factory multiboot image,
verifies all four images and metadata, then releases reset. This is also the recovery
path for a damaged bootloader.

## RTL and host-software deliverables

- Adapt the TinyFPGA bootloader to the Cherry pinout, 48 MHz clock, PROG LED,
  W25Q32 geometry, and chosen flash address map.
- Generate the cold-boot applet and four-entry vector table for images 0-3.
- Keep the bootloader CDC protocol compatible with `tinyprog` where practical,
  but maintain a Cherry-owned host tool/fork rather than depending on obsolete
  web update endpoints.
- Add a common USB BOOT service to all four images. It accepts only framed
  `BOOT n` commands, validates `n` and the destination manifest, and drives
  `SB_WARMBOOT` with the requested two-bit selector.
- Fix the functional endpoint assignment to EP1=BOOT, EP2=FLASH, and EP3=UART.
  Each function receives its own OUT/IN endpoint pair and FIFO; no function
  parser may inspect or consume another function's payload.
- In images 1-3, keep BOOT management traffic on EP1 and the UART byte stream on
  EP3. An escape sequence embedded in arbitrary user UART data is not acceptable
  because it could cause an accidental reboot.
- Instantiate the FLASH service only in image 0. Images 1-3 do not enumerate or
  enable its command/data endpoint and must report FLASH requests unsupported.
- Instantiate the UART service only in images 1-3. Image 0 uses USB bandwidth
  for BOOT and FLASH and does not expose the user UART stream.
- Expose the user USB channel as byte-stream ready/valid interfaces to HDL. It
  is a USB-to-byte-stream block, not an external asynchronous UART.
- Add a flash-quiesce handshake between the manager and user logic. Before warm
  boot, the manager blocks new QSPI requests, waits for idle/WIP-clear, restores
  ordinary SPI command mode, raises `/CS`, disconnects USB, and asserts
  `SB_WARMBOOT` with the requested `S1:S0` value.
- Extend the host tool to detect whether a user image or bootloader is active,
  issue `BOOT 0`, wait for bootloader re-enumeration, program a selected image
  slot, verify its manifest/CRC, issue `BOOT n`, and wait for the selected user
  image to enumerate.
- Provide a minimal user-image example that implements USB loopback/hello-world,
  controls the D+ pull-up, includes the boot manager, keeps `prog_active` low,
  and does not modify protected flash regions.
- Generate the factory image with the cold-boot table, all four valid images,
  and board metadata.
- Allocate valid USB VID/PID values before distributing hardware. Use distinct
  product identities for the bootloader and standard user wrapper so host tools
  can distinguish the re-enumerated device.

## Schematic and PCB work

- Remove the FT2232H and all dedicated FTDI power, reset, reference, USB,
  MPSSE, UART, and contention-guard parts after tracing every shared net.
- Reconnect the USB pair, pull-up control, CBSEL mode switch, USER button, PROG
  LED, QSPI IO2/IO3, regulator enables, and programming header as described
  above.
- Reassign or remove expansion-header labels for B4/A4/A3/G5/H5/H4. J8 and H9
  were previously internal UART connections and are repurposed. Only GPIO 1-36
  remain published on J2/J3; GPIO 37-53 are not fitted on expansion headers.
- Place USB resistors near the FPGA, ESD protection near the connector, and QSPI
  pull-ups near the flash. Reuse the right-edge six-pin header for GND,
  `CRESET_B`, and four-wire SPI programming; remove the redundant J4, J6, and
  dedicated recovery header J7.
- Update the silkscreen with unambiguous `IMAGE 1`, `IMAGE 0`, binary switch
  values, `RESET`, `USER`, `SPI`, and `PROG` LED labels.

## Verification gates

- ERC passes with zero violations.
- PCB DRC and schematic parity pass, with only documented project baseline
  warnings.
- Both rails fall below the FPGA/flash power-off threshold while RESET is held
  and restart cleanly on release.
- Switch value `00` plus RESET directly selects image 0 and always enumerates
  the bootloader, with no timing-dependent button sequence.
- Programming erases, writes, and verifies each of images 1-3 without changing
  image 0, security-register metadata, another image, or user data.
- Switch values `01`, `10`, and `11` directly select images 1, 2, and 3 without
  first executing the bootloader.
- From every image, `BOOT 0/1/2/3` reaches or deliberately restarts the requested
  valid image.
- In images 1-3, ordinary UART data cannot trigger a reboot and FLASH commands
  are unavailable.
- In image 0, FLASH commands work and the UART service is unavailable.
- USB descriptors and endpoint routing match EP1=BOOT, EP2=FLASH, EP3=UART in
  every image; traffic injected into one endpoint never appears in another
  service FIFO.
- Continuous EP3 UART traffic cannot starve an EP1 BOOT request, and sustained
  EP2 flash transfers in image 0 still leave EP1 responsive.
- A deliberately invalid user image remains recoverable with `00` plus RESET.
- With the switch at production value `01`, power-up starts image 1 without a
  USB host or any bootloader timeout.
- Runtime single, dual, and quad flash reads pass across voltage and temperature
  targets; a subsequent RESET still cold-boots successfully.
- USB enumeration and sustained bidirectional CDC transfer pass on Linux,
  Windows, and macOS through representative USB-C cables and hubs.
- External factory programming works on an otherwise blank board.

## Implementation order

1. Prove the adapted bootloader, four-way cold-boot selection, user USB manager,
   and user CDC wrapper on an existing TinyFPGA BX or wired Cherry prototype.
2. Freeze the multiboot format, slot addresses, metadata, and recovery protocol.
3. Update the schematic and run ERC.
4. Complete PCB routing and run final DRC plus schematic parity. Component
   placement and the placement-stage parity check are complete.
5. Update constraints, build scripts, README, boot documentation, BOM, and
   manufacturing instructions.
6. Assemble prototypes and execute the verification gates above before release.

## Primary references

- TinyFPGA BX hardware: <https://github.com/tinyfpga/TinyFPGA-BX>
- TinyFPGA USB bootloader and protocol: <https://github.com/tinyfpga/TinyFPGA-Bootloader>
- Maintained USB CDC/compatible bootloader reference: <https://github.com/ulixxe/usb_cdc>
- iCE40 programming and multiboot technical note: <https://www.latticesemi.com/-/media/LatticeSemi/Documents/ApplicationNotes/IK/FPGA-TN-02001-3-4-iCE40-Programming-Configuration.ashx?document_id=46502>
- TPS62A02 regulator data sheet: <https://www.ti.com/lit/ds/symlink/tps62a02.pdf>
