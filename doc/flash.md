# CDC Flash Protocol

[日本語](flash.ja.md)

This document defines the serial framing, boot management, flash programming,
and user-data channels shared by NextMicon Cherry FPGA images, the `nmb` host
tool, and Web Serial applications. The multiboot sequence and flash map are
described in [boot.md](boot.md).

The Rust host in `flash/cli` and the static Web Serial application in
`flash/web` implement this protocol. The corresponding CDC ACM USB engine and
frame handlers in the Cherry HDL remain to be implemented.

## Transport choice

Every image enumerates as the same USB CDC ACM serial device. BOOT, FLASH, and
UART are logical channels inside a framed serial byte stream; they are not
separate USB endpoints. This lets native applications use the operating
system's serial driver and lets compatible browsers program a board through
Web Serial.

The stream is always framed. User UART bytes are carried as UART-channel frame
payloads and are never scanned for a reboot escape sequence.

## USB CDC ACM profile

Cherry is a USB 2.0 Full-Speed, bus-powered device. It uses a 48 MHz FPGA clock
and operates at 12 Mbit/s.

| Purpose | Interface/endpoint | Type | Max packet |
| --- | --- | --- | ---: |
| Standard and CDC requests | EP0 | Control | 64 bytes |
| CDC notification | EP1 IN `0x81` | Interrupt | 16 bytes |
| CDC serial host-to-FPGA | EP2 OUT `0x02` | Bulk | 64 bytes |
| CDC serial FPGA-to-host | EP2 IN `0x82` | Bulk | 64 bytes |

The CDC function contains one Communication Class interface and one Data Class
interface with Header, Call Management, ACM, and Union functional descriptors.
It supports at least:

- standard USB enumeration and endpoint-halt requests;
- `SET_LINE_CODING` and `GET_LINE_CODING`;
- `SET_CONTROL_LINE_STATE`;
- CDC `SERIAL_STATE` notification on EP1 IN.

The nominal host setting is 115200, 8 data bits, no parity, and 1 stop bit.
Because this is a synchronous USB stream, the baud-rate field does not control
wire speed. DTR, RTS, baud-rate changes, and BREAK must never select an FPGA
image or erase flash.

### Stable device identity

The `boot` and `user` images use the same VID, PID, manufacturer, product, and serial
number. Active image and capabilities are obtained with the framed GET_INFO
command. Keeping one USB identity simplifies OS and Web Serial permission
handling across FPGA reconfiguration.

| String | Value/requirement |
| --- | --- |
| Manufacturer | `NextMicon` |
| Product | `NextMicon Cherry` |
| Serial number | Stable and unique for one physical board |

Production VID/PID values are not allocated yet. Example or borrowed IDs must
not ship in a product. Until allocation, `nmb` can recognize the manufacturer
and product strings; `--usb-id VID:PID` provides an explicit filter.

The D+ pull-up remains disabled until the selected image has initialized USB.
For warm boot, the device finishes the response frame and its CDC IN transfer,
disables the pull-up, reconfigures, and enumerates again with the same identity.

## Wire framing

Each message is COBS encoded and terminated by one `0x00` byte:

```text
COBS(decoded frame) 00
```

COBS encoded data never contains zero, so a receiver can recover frame
boundaries after an error by scanning for the next `0x00`. USB read boundaries
have no protocol meaning; a read may contain a partial frame or several frames.

### Decoded frame

| Offset | Size | Field |
| ---: | ---: | --- |
| 0 | 1 | Protocol version, currently `0x01` |
| 1 | 1 | Channel |
| 2 | 1 | Opcode |
| 3 | 1 | Sequence number |
| 4 | 2 | Payload length, little-endian |
| 6 | 0-256 | Payload |
| 6+length | 4 | CRC-32/ISO-HDLC, little-endian |

CRC covers the six-byte header and payload, but not the CRC field, COBS
overhead, or trailing delimiter. Parameters are polynomial `0x04c11db7`,
initial value `0xffffffff`, reflected input/output, and final XOR
`0xffffffff`.

| Limit | Value |
| --- | ---: |
| Maximum payload | 256 bytes |
| Maximum decoded frame | 266 bytes |
| Maximum encoded frame including delimiter | 269 bytes |

A receiver silently discards an invalid COBS frame, unsupported version,
length mismatch, oversized frame, or CRC mismatch. It must continue scanning
at the next delimiter.

### Channels, opcodes, and sequencing

| Channel | Value | `boot` | `user` |
| --- | ---: | --- | --- |
| BOOT | `0x01` | Available | Available |
| FLASH | `0x02` | Available | Unavailable |
| UART | `0x03` | Unavailable | Available |

For BOOT and FLASH, the host sends only one request at a time. The response
copies the channel and sequence number and sets bit 7 of the request opcode:

```text
response opcode = request opcode | 0x80
```

The sequence number wraps modulo 256. It prevents a delayed or stale frame
from satisfying a newer request. UART DATA is unacknowledged; its sequence
number is diagnostic and may wrap independently.

## BOOT channel `0x01`

### GET_INFO `0x00`

Request payload is empty. Response opcode is `0x80` and its payload is:

| Offset | Size | Field |
| ---: | ---: | --- |
| 0 | 1 | BOOT status; `0x00` on success |
| 1 | 1 | Active image: `0` (`boot`) or `1` (`user`) |
| 2 | 1 | Capability bitmap |

Capability bits are `0x01` BOOT, `0x02` FLASH, and `0x04` UART. `boot` reports
`0x03`; `user` reports `0x05`. Reserved bits are zero.

### SELECT_IMAGE `0x01`

Request payload is one target-image byte: `0` for `boot` or `1` for `user`.
Values 2 through 255 are invalid. Response opcode is `0x81`; response payload
is one BOOT status byte.

| Status | Meaning |
| ---: | --- |
| `0x00` | Accepted |
| `0x01` | Invalid image or malformed payload |
| `0x02` | Destination manifest or CRC is invalid |
| `0x03` | Boot/flash manager is busy |

For Accepted, the complete response frame must reach the host before USB is
disconnected. The FPGA then quiesces QSPI, exits persistent QPI mode, raises
flash `/CS`, and asserts `SB_WARMBOOT`. A rejected command leaves the current
image running.

## FLASH channel `0x02`

Every FLASH response payload starts with one status byte.

| Status | Meaning |
| ---: | --- |
| `0x00` | Accepted/completed |
| `0x01` | Invalid or unavailable command |
| `0x02` | Invalid address, length, or slot |
| `0x03` | Write-protected region |
| `0x04` | Flash/boot manager busy |
| `0x05` | SPI flash I/O failure |

### ERASE_SLOT `0x01`

Request payload is the fixed user-slot byte `1`. Response opcode is `0x81` with
one status byte. On success, the complete 256 KiB user slot is erased and WIP
is clear before the response is sent. The boot region is always protected.

### WRITE `0x02`

| Payload offset | Size | Field |
| ---: | ---: | --- |
| 0 | 3 | 24-bit flash address, little-endian |
| 3 | 1-253 | Data |

Response opcode is `0x82` with one status byte. On success, all data is
programmed and WIP is clear before the response. The FPGA splits a frame at SPI
page boundaries when necessary. USB writes are restricted to the user image
(`0x040000-0x07ffff`). The boot region is protected in hardware.

### READ `0x03`

| Payload offset | Size | Field |
| ---: | ---: | --- |
| 0 | 3 | 24-bit flash address, little-endian |
| 3 | 2 | Requested length, little-endian (`1` through `255`) |

Response opcode is `0x83`. Its payload is status `0x00` followed by exactly the
requested bytes. The range must remain inside the 4 MiB main flash. `nmb`
verifies the complete bitstream and manifest through READ.

User-data erase/write commands are reserved for a future protocol revision.

## Image manifest

The final 32 bytes of the 256 KiB user image contain a manifest. Raw
bitstreams may be at most 262,112 bytes. The manifest is programmed last.

| Offset | Size | Field |
| ---: | ---: | --- |
| 0 | 4 | ASCII `NMF1` |
| 4 | 1 | Manifest version `1` |
| 5 | 1 | User image number, always `1` |
| 6 | 2 | Flags, zero |
| 8 | 4 | Bitstream length, little-endian |
| 12 | 4 | CRC-32/ISO-HDLC, little-endian |
| 16 | 16 | Reserved, all `0xff` |

Manifest CRC covers exactly the bitstream-length bytes from the slot base.
Erased padding and the manifest are excluded. BOOT validates magic, version,
image number, bounded nonzero length, and CRC before accepting a target.

## UART channel `0x03`

UART DATA opcode is `0x01`. Its payload contains 0 through 256 user bytes.
Frames in either direction are unacknowledged. Packet and frame boundaries
have no meaning to the user byte stream; bytes remain ordered and must not be
silently dropped. FIFO backpressure must propagate to the CDC Bulk endpoints.

The UART channel is not directly terminal-compatible because its bytes are
framed. A host console must add and remove UART frames. This prevents arbitrary
user data from ever being interpreted as a BOOT command.

## Native `nmb` workflow

`nmb` enumerates CDC ports, filters by USB identity or NextMicon strings, and
uses the stable serial number as `cherry-<serial>`.

```sh
nmb ls
nmb boot cherry-0123 user
nmb flash cherry-0123 image.bin --boot
```

Before flashing, `nmb` sends GET_INFO. If `user` is active, it requests `boot`,
waits for the same serial number to re-enumerate, confirms `boot` with GET_INFO,
then erases, writes, manifests, and reads back the user image. There is no
destination argument because only one user image exists.

## Web Serial flashing

`flash/web` is a pnpm-managed React and Tailwind CSS application. It compiles
the Rust protocol library used by `nmb` to WebAssembly, while JavaScript owns
Web Serial transport and UI state. No native USB driver is required. Browser
requirements and API behavior are defined by the
[Web Serial specification](https://wicg.github.io/serial/). It asks the user
for a serial port and opens the CDC port at the nominal baud rate:

```js
const port = await navigator.serial.requestPort();
await port.open({ baudRate: 115200, bufferSize: 4096 });
```

The application does the following:

1. reads arbitrary chunks from `port.readable` and splits them at `0x00`;
2. passes each frame to Rust WASM for COBS decoding and CRC checking;
3. matches management responses by channel, response opcode, and sequence;
4. selects a local bitstream with a file picker;
5. uses GET_INFO, SELECT_IMAGE, ERASE_SLOT, WRITE, and READ exactly as `nmb`;
6. closes readers/writers on disconnect and reopens after warm-boot enumeration.

Install dependencies and start Vite from a secure localhost context, then open
the displayed URL in a supporting Chromium-based browser:

```sh
cd flash/web
pnpm install
pnpm dev
```

`pnpm build` rebuilds the Rust WASM package and writes a production bundle to
`flash/web/dist`.

### WASM JSON boundary

The WASM library exports `encodeMessageJson`, `decodeMessageJson`, and `crc32`.
The first two functions convert between a complete wire frame and this JSON
representation:

```json
{"version":1,"channel":2,"opcode":3,"sequence":7,"payload":[0,0,4,255,0]}
```

All fields are required, unknown fields are rejected, and `payload` is an array
of byte values. `encodeMessageJson` returns COBS-encoded bytes with the trailing
`0x00`; `decodeMessageJson` validates COBS, length, version, channel, and CRC
before returning JSON. This keeps wire-format validation identical in `nmb`
and the browser.

Web Serial is available only in supporting browsers and secure contexts. Port
selection requires explicit user permission and normally a user gesture.
`navigator.serial.getPorts()` may return previously authorized ports, but a
browser may require the user to select the device again after disconnect. A
web flasher must detect this and present a reconnect action instead of assuming
automatic access.

The app waits up to 15 seconds for an already-authorized port with the same
USB VID/PID and confirms the active image using GET_INFO. If multiple boards
with the same USB identity are authorized, attach only the board being flashed
during automatic re-enumeration.

The web page cannot bypass device-side protection: `boot` remains unwritable,
addresses are checked by the FPGA, and every written byte is read back. The
bitstream can remain entirely local to the browser; uploading it to a server is
not required.

## Incomplete implementation items

- Production USB VID/PID allocation and final power descriptor
- FPGA USB Full-Speed physical/packet engine
- CDC ACM descriptors, standard requests, and notification endpoint
- COBS encoder/decoder and CRC32 frame engine in HDL
- BOOT/FLASH/UART channel dispatch and FIFOs in HDL
- Framed UART console command in `nmb`

These items must preserve the frame and flash formats defined here.
