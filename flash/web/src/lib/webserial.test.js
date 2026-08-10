import assert from "node:assert/strict";
import test from "node:test";

import "./wasm-setup.js";
import { Channel, decodeFrame, encodeFrame, responseOpcode } from "./protocol.js";
import { WebSerialTransport } from "./webserial.js";

class FakeSerialPort {
  readable = null;
  writable = null;
  #controller = null;
  #respond;

  constructor(respond = true) {
    this.#respond = respond;
  }

  async open() {
    this.readable = new ReadableStream({
      start: (controller) => {
        this.#controller = controller;
      },
    });
    this.writable = new WritableStream({
      write: (wire) => {
        if (!this.#respond) {
          return;
        }
        const request = decodeFrame(wire);
        const response = encodeFrame({
          channel: request.channel,
          opcode: responseOpcode(request.opcode),
          sequence: request.sequence,
          payload: Uint8Array.of(0, 2, 5),
        });
        const split = Math.floor(response.length / 2);
        this.#controller.enqueue(response.subarray(0, split));
        this.#controller.enqueue(response.subarray(split));
      },
    });
  }

  async close() {
    this.readable = null;
    this.writable = null;
    this.#controller = null;
  }
}

test("Web Serial transport matches a response split across stream chunks", async () => {
  const port = new FakeSerialPort();
  const transport = new WebSerialTransport(port);
  await transport.open();
  const response = await transport.exchange(
    { channel: Channel.BOOT, opcode: 0, sequence: 19, payload: new Uint8Array() },
    100,
  );
  assert.equal(response.sequence, 19);
  assert.deepEqual(response.payload, Uint8Array.of(0, 2, 5));
  await transport.close();
});

test("Web Serial transport rejects a timed-out request", async () => {
  const port = new FakeSerialPort(false);
  const transport = new WebSerialTransport(port);
  await transport.open();
  await assert.rejects(
    transport.exchange(
      { channel: Channel.BOOT, opcode: 0, sequence: 0, payload: new Uint8Array() },
      5,
    ),
    /timed out/,
  );
  await transport.close();
});
