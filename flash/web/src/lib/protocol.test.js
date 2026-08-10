import assert from "node:assert/strict";
import test from "node:test";

import "./wasm-setup.js";
import {
  Channel,
  FlashCommand,
  FrameDecoder,
  crc32,
  decodeFrame,
  encodeFrame,
} from "./protocol.js";

test("CRC32 matches the ISO-HDLC check value", () => {
  assert.equal(crc32(new TextEncoder().encode("123456789")), 0xcbf43926);
});

test("Rust WASM converts JSON messages and wire frames", () => {
  const payload = Uint8Array.from({ length: 256 }, (_, index) => index);
  const expected = { channel: Channel.FLASH, opcode: FlashCommand.WRITE, sequence: 42, payload };
  const wire = encodeFrame(expected);
  assert.ok(wire.length <= 269);
  assert.equal(wire.at(-1), 0);
  assert.deepEqual(decodeFrame(wire), expected);
});

test("corrupted frames are rejected", () => {
  const wire = encodeFrame({
    channel: Channel.FLASH,
    opcode: FlashCommand.WRITE,
    sequence: 3,
    payload: Uint8Array.of(1, 2, 3),
  });
  wire[3] ^= 0x40;
  assert.throws(() => decodeFrame(wire), /CRC|COBS|version|channel/);
});

test("stream decoder accepts partial and multiple frames and recovers from garbage", () => {
  const errors = [];
  const decoder = new FrameDecoder({ onError: (error) => errors.push(error) });
  const first = encodeFrame({ channel: Channel.BOOT, opcode: 0, sequence: 1 });
  const second = encodeFrame({ channel: Channel.BOOT, opcode: 1, sequence: 2, payload: [3] });

  assert.deepEqual(decoder.push(first.subarray(0, 3)), []);
  const combined = new Uint8Array(first.length - 3 + 3 + second.length);
  combined.set(first.subarray(3));
  combined.set([1, 0xff, 0], first.length - 3);
  combined.set(second, first.length);
  const frames = decoder.push(combined);

  assert.equal(frames.length, 2);
  assert.equal(frames[0].sequence, 1);
  assert.equal(frames[1].sequence, 2);
  assert.equal(errors.length, 1);
});
