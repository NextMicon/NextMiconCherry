import initWasm, {
  crc32 as wasmCrc32,
  decodeMessageJson,
  encodeMessageJson,
} from "../wasm/pkg/nextmicon_flash.js";

const FRAME_VERSION = 1;
const FRAME_DELIMITER = 0;
const FRAME_MAX_WIRE_SIZE = 269;
const RESPONSE_BIT = 0x80;

export const Channel = Object.freeze({
  BOOT: 0x01,
  FLASH: 0x02,
  UART: 0x03,
});

export const BootCommand = Object.freeze({
  GET_INFO: 0x00,
  SELECT_IMAGE: 0x01,
});

export const FlashCommand = Object.freeze({
  ERASE_SLOT: 0x01,
  WRITE: 0x02,
  READ: 0x03,
});

let wasmInitialization = null;

export function initProtocolWasm(moduleOrPath) {
  if (!wasmInitialization) {
    const input = moduleOrPath === undefined ? undefined : { module_or_path: moduleOrPath };
    wasmInitialization = initWasm(input).catch((error) => {
      wasmInitialization = null;
      throw error;
    });
  }
  return wasmInitialization;
}

export function crc32(bytes) {
  return wasmCrc32(asBytes(bytes));
}

export function responseOpcode(opcode) {
  return opcode | RESPONSE_BIT;
}

export function encodeFrame({ channel, opcode, sequence, payload = new Uint8Array() }) {
  return encodeMessageJson(
    JSON.stringify({
      version: FRAME_VERSION,
      channel,
      opcode,
      sequence,
      payload: Array.from(asBytes(payload)),
    }),
  );
}

export function decodeFrame(input) {
  const message = JSON.parse(decodeMessageJson(asBytes(input)));
  return {
    channel: message.channel,
    opcode: message.opcode,
    sequence: message.sequence,
    payload: Uint8Array.from(message.payload),
  };
}

export class FrameDecoder {
  #encoded = [];
  #discarding = false;
  #onError;

  constructor({ onError = () => {} } = {}) {
    this.#onError = onError;
  }

  push(chunk) {
    const frames = [];
    for (const byte of asBytes(chunk)) {
      if (byte === FRAME_DELIMITER) {
        if (!this.#discarding && this.#encoded.length > 0) {
          try {
            frames.push(decodeFrame(Uint8Array.from([...this.#encoded, FRAME_DELIMITER])));
          } catch (error) {
            this.#onError(error);
          }
        }
        this.#encoded = [];
        this.#discarding = false;
      } else if (!this.#discarding) {
        if (this.#encoded.length >= FRAME_MAX_WIRE_SIZE - 1) {
          this.#encoded = [];
          this.#discarding = true;
          this.#onError(new Error("encoded frame exceeds the wire-size limit"));
        } else {
          this.#encoded.push(byte);
        }
      }
    }
    return frames;
  }

  reset() {
    this.#encoded = [];
    this.#discarding = false;
  }
}

export function concatBytes(...parts) {
  const arrays = parts.map(asBytes);
  const output = new Uint8Array(arrays.reduce((total, bytes) => total + bytes.length, 0));
  let offset = 0;
  for (const bytes of arrays) {
    output.set(bytes, offset);
    offset += bytes.length;
  }
  return output;
}

function asBytes(value) {
  if (value instanceof Uint8Array) {
    return value;
  }
  if (ArrayBuffer.isView(value)) {
    return new Uint8Array(value.buffer, value.byteOffset, value.byteLength);
  }
  if (value instanceof ArrayBuffer) {
    return new Uint8Array(value);
  }
  return Uint8Array.from(value);
}
