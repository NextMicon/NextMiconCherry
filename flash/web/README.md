# NextMicon Web Flasher

The Web Serial flasher is a Vite application built with React, Tailwind CSS,
and pnpm. The Rust library behind the `nmb` CLI is compiled to WebAssembly, so
the browser and CLI share the same COBS framing and CRC32 implementation.
JavaScript handles Web Serial, flash operations, reconnect state, and the UI.

The app erases a user slot, writes the bitstream and `NMF1` manifest, reads
both back, and optionally warm-boots the new image. Files remain in the browser
and are not uploaded.

## Requirements

- Node.js 22.12 or later
- pnpm 11
- Rust with the `wasm32-unknown-unknown` target
- `wasm-pack`
- A Chromium-based browser with Web Serial support

Install the Rust tooling once if needed:

```sh
rustup target add wasm32-unknown-unknown
cargo install wasm-pack
```

## Run locally

```sh
cd flash/web
pnpm install
pnpm dev
```

Open the localhost URL printed by Vite, choose the NextMicon serial device,
select a `.bin` bitstream and image 1-3, and start flashing. Image 0 remains
protected. The `dev`, `test`, and `build` scripts rebuild the Rust WASM package
before running their main command.

Warm boot temporarily removes the serial port. The app waits up to 15 seconds
for an already-authorized port with the same USB VID/PID and confirms the
active image with GET_INFO. If automatic reopening is not allowed by the
browser, use **デバイスを選択** again. With multiple identical authorized
boards attached, connect only the board being flashed during re-enumeration.

## Test and build

```sh
pnpm test
pnpm lint
pnpm build
```

The production application is written to `dist/`. Protocol and mock flash
tests run in Node using the same generated WASM binary as the browser.

The complete wire specification is in [`doc/flash.md`](../../doc/flash.md).
