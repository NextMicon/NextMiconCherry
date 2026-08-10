import assert from "node:assert/strict";
import test from "node:test";

import "./wasm-setup.js";
import { Channel, BootCommand, FlashCommand, responseOpcode } from "./protocol.js";
import {
  CAPABILITY_BOOT,
  CAPABILITY_FLASH,
  FLASH_END,
  IMAGE_SLOT_SIZE,
  MANIFEST_SIZE,
  NextMiconClient,
  createManifest,
} from "./client.js";

class FakeTransport {
  constructor() {
    this.memory = new Uint8Array(FLASH_END).fill(0xff);
    this.activeImage = 0;
    this.sequences = [];
  }

  async exchange(request) {
    this.sequences.push(request.sequence);
    let payload;
    if (request.channel === Channel.BOOT && request.opcode === BootCommand.GET_INFO) {
      payload = Uint8Array.of(0, this.activeImage, CAPABILITY_BOOT | CAPABILITY_FLASH);
    } else if (request.channel === Channel.BOOT && request.opcode === BootCommand.SELECT_IMAGE) {
      this.activeImage = request.payload[0];
      payload = Uint8Array.of(0);
    } else if (request.channel === Channel.FLASH && request.opcode === FlashCommand.ERASE_SLOT) {
      const image = request.payload[0];
      this.memory.fill(0xff, image * IMAGE_SLOT_SIZE, (image + 1) * IMAGE_SLOT_SIZE);
      payload = Uint8Array.of(0);
    } else if (request.channel === Channel.FLASH && request.opcode === FlashCommand.WRITE) {
      const address = decodeAddress(request.payload);
      for (let index = 3; index < request.payload.length; index += 1) {
        this.memory[address + index - 3] &= request.payload[index];
      }
      payload = Uint8Array.of(0);
    } else if (request.channel === Channel.FLASH && request.opcode === FlashCommand.READ) {
      const address = decodeAddress(request.payload);
      const length = request.payload[3] | (request.payload[4] << 8);
      payload = new Uint8Array(length + 1);
      payload.set(this.memory.subarray(address, address + length), 1);
    } else {
      payload = Uint8Array.of(1);
    }
    return {
      channel: request.channel,
      opcode: responseOpcode(request.opcode),
      sequence: request.sequence,
      payload,
    };
  }
}

test("manifest has the NMF1 layout and erased reserved bytes", () => {
  const data = new TextEncoder().encode("fpga bitstream");
  const manifest = createManifest(2, data);
  assert.equal(new TextDecoder().decode(manifest.bytes.subarray(0, 4)), "NMF1");
  assert.equal(manifest.bytes[4], 1);
  assert.equal(manifest.bytes[5], 2);
  assert.equal(new DataView(manifest.bytes.buffer).getUint32(8, true), data.length);
  assert.ok(manifest.bytes.subarray(16).every((value) => value === 0xff));
});

test("client programs the bitstream and manifest, then verifies both", async () => {
  const transport = new FakeTransport();
  const client = new NextMiconClient(transport, { timeoutMs: 100 });
  const data = Uint8Array.from({ length: 600 }, (_, index) => index);
  const updates = [];
  const manifest = await client.programImage(2, data, (progress) => updates.push(progress));

  const base = 2 * IMAGE_SLOT_SIZE;
  const manifestAddress = 3 * IMAGE_SLOT_SIZE - MANIFEST_SIZE;
  assert.deepEqual(transport.memory.slice(base, base + data.length), data);
  assert.deepEqual(
    transport.memory.slice(manifestAddress, manifestAddress + MANIFEST_SIZE),
    manifest.bytes,
  );
  assert.equal(updates.at(-1).completed, updates.at(-1).total);
  assert.deepEqual(transport.sequences.slice(0, 4), [0, 1, 2, 3]);
});

test("image zero and invalid image sizes are rejected", () => {
  assert.throws(() => createManifest(0, Uint8Array.of(1)), /protected/);
  assert.throws(() => createManifest(1, new Uint8Array()), /empty/);
});

function decodeAddress(payload) {
  return payload[0] | (payload[1] << 8) | (payload[2] << 16);
}
