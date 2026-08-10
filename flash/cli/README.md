# NextMicon Flash CLI

`nmb` is the host-side programmer and image manager for NextMicon Cherry. Both
FPGA images enumerate as the same CDC ACM serial device. COBS-delimited frames
inside that serial stream provide independent BOOT, FLASH, and UART channels.

The complete wire format, including Web Serial usage, is documented in
[`doc/flash.md`](../../doc/flash.md).

## Build

```sh
cargo build --release
```

The executable is `target/release/nmb`. Linux users need permission to open the
CDC device, typically through the distribution's serial-port group or a udev
rule. Windows and macOS use their CDC ACM drivers.

### WebAssembly library

The library can also be built for the Web flasher:

```sh
wasm-pack build --target web --out-dir ../web/src/wasm/pkg --release
```

It exports `encodeMessageJson`, `decodeMessageJson`, and `crc32`.
`encodeMessageJson` converts a JSON message to the COBS-delimited wire frame;
`decodeMessageJson` validates and converts a wire frame back to JSON. The
generated package is consumed by `flash/web` and is not committed.

## Commands

List connected boards:

```console
$ nmb ls
cherry-0123

$ nmb ls --verbose
cherry-0123    boot    1234:0001    /dev/ttyACM0    NextMicon Cherry
```

Production VID/PID values are not allocated yet. By default `nmb` recognizes
the `NextMicon` manufacturer and `NextMicon Cherry` product strings. Discovery
can be restricted explicitly:

```sh
nmb --usb-id 1234:0001 ls
```

Warm boot either role:

```sh
nmb boot <board> <boot|user>
```

Erase, program, manifest, and read back the user image:

```sh
nmb flash <board> <bitstream.bin>
```

Start the image after successful verification:

```sh
nmb flash <board> <bitstream.bin> --boot
```

Before programming, `nmb` queries GET_INFO. If `user` is active, it requests
`boot`, waits for the same USB serial number to re-enumerate, verifies GET_INFO,
and then programs the single user image. `boot` is always protected;
factory/recovery updates use the external SPI header.

Use `nmb --help` or `nmb <command> --help` for all options. One framed request
defaults to a 30-second timeout and re-enumeration defaults to 15 seconds.

## Implementation

- `protocol.rs`: COBS framing, CRC32, channels, commands, and flash constants
- `message.rs`: validated JSON representation of a protocol frame
- `wasm.rs`: WASM exports for wire/JSON conversion and CRC32
- `serial.rs`: CDC port discovery, opening, streaming frame parser, and response matching
- `client.rs`: GET_INFO, BOOT, protected FLASH programming, and readback verification
- `manifest.rs`: 32-byte `NMF1` image manifest

The Rust host implementation and mock-device tests are complete. The matching
CDC ACM and frame engine still need to be implemented in Cherry HDL before a
physical board can answer the commands.
