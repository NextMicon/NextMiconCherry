import { readFile } from "node:fs/promises";

import { initProtocolWasm } from "./protocol.js";

const wasm = await readFile(new URL("../wasm/pkg/nextmicon_flash_bg.wasm", import.meta.url));
await initProtocolWasm(wasm);
