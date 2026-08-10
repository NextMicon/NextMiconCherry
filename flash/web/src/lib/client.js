import {
  BootCommand,
  Channel,
  FlashCommand,
  concatBytes,
  crc32,
} from "./protocol.js";

export const CAPABILITY_BOOT = 1 << 0;
export const CAPABILITY_FLASH = 1 << 1;
export const BOOT_IMAGE = 0;
export const USER_IMAGE = 1;

export const IMAGE_SLOT_SIZE = 0x04_0000;
export const FLASH_END = 0x40_0000;
export const MANIFEST_SIZE = 32;
export const MAX_IMAGE_SIZE = IMAGE_SLOT_SIZE - MANIFEST_SIZE;
export const FLASH_WRITE_DATA_SIZE = 253;
export const FLASH_READ_DATA_SIZE = 255;

const BOOT_STATUS = ["Accepted", "Invalid image", "Invalid manifest", "Busy"];
const FLASH_STATUS = [
  "Accepted",
  "Invalid command",
  "Invalid address",
  "Write protected",
  "Busy",
  "Flash I/O error",
];

export class NextMiconClient {
  #transport;
  #sequence = 0;
  #timeoutMs;

  constructor(transport, { timeoutMs = 30_000 } = {}) {
    this.#transport = transport;
    this.#timeoutMs = timeoutMs;
  }

  async getInfo() {
    const payload = await this.#request(Channel.BOOT, BootCommand.GET_INFO);
    requireLength(payload, 3, "BOOT GET_INFO");
    checkStatus(payload[0], BOOT_STATUS, "BOOT");
    if (payload[1] > USER_IMAGE) {
      throw new Error(`device reported invalid image ${payload[1]}`);
    }
    if ((payload[2] & CAPABILITY_BOOT) === 0) {
      throw new Error(`device reported invalid capabilities 0x${hexByte(payload[2])}`);
    }
    return { activeImage: payload[1], capabilities: payload[2] };
  }

  async selectImage(image) {
    requireImage(image);
    const payload = await this.#request(
      Channel.BOOT,
      BootCommand.SELECT_IMAGE,
      Uint8Array.of(image),
    );
    requireLength(payload, 1, "BOOT SELECT_IMAGE");
    checkStatus(payload[0], BOOT_STATUS, "BOOT");
  }

  async eraseUserImage() {
    const payload = await this.#request(
      Channel.FLASH,
      FlashCommand.ERASE_SLOT,
      Uint8Array.of(USER_IMAGE),
    );
    requireLength(payload, 1, "FLASH ERASE_SLOT");
    checkStatus(payload[0], FLASH_STATUS, "FLASH");
  }

  async writeAt(address, data, onChunk = () => {}) {
    let offset = 0;
    const bytes = toBytes(data);
    if (bytes.length === 0) {
      throw new Error("FLASH WRITE data is empty");
    }
    requireFlashRange(address, bytes.length);

    while (offset < bytes.length) {
      const length = Math.min(FLASH_WRITE_DATA_SIZE, bytes.length - offset);
      const chunk = bytes.subarray(offset, offset + length);
      const payload = concatBytes(encodeAddress(address + offset), chunk);
      const response = await this.#request(Channel.FLASH, FlashCommand.WRITE, payload);
      requireLength(response, 1, "FLASH WRITE");
      checkStatus(response[0], FLASH_STATUS, "FLASH");
      offset += length;
      onChunk(length);
    }
  }

  async readAt(address, length) {
    if (!Number.isInteger(length) || length < 1 || length > FLASH_READ_DATA_SIZE) {
      throw new Error(`invalid FLASH READ length ${length}`);
    }
    requireFlashRange(address, length);
    const request = new Uint8Array(5);
    request.set(encodeAddress(address));
    new DataView(request.buffer).setUint16(3, length, true);
    const response = await this.#request(Channel.FLASH, FlashCommand.READ, request);
    requireLength(response, length + 1, "FLASH READ");
    checkStatus(response[0], FLASH_STATUS, "FLASH");
    return response.slice(1);
  }

  async verifyAt(address, expected, onChunk = () => {}) {
    const bytes = toBytes(expected);
    requireFlashRange(address, bytes.length);
    let offset = 0;
    while (offset < bytes.length) {
      const length = Math.min(FLASH_READ_DATA_SIZE, bytes.length - offset);
      const actual = await this.readAt(address + offset, length);
      for (let index = 0; index < length; index += 1) {
        if (actual[index] !== bytes[offset + index]) {
          const location = address + offset + index;
          throw new Error(
            `flash verification failed at 0x${location.toString(16).padStart(6, "0")}: ` +
              `expected 0x${hexByte(bytes[offset + index])}, got 0x${hexByte(actual[index])}`,
          );
        }
      }
      offset += length;
      onChunk(length);
    }
  }

  async programUserImage(data, onProgress = () => {}) {
    const bytes = toBytes(data);
    const manifest = createUserManifest(bytes);
    const manifestAddress = (USER_IMAGE + 1) * IMAGE_SLOT_SIZE - MANIFEST_SIZE;
    const total = bytes.length * 2 + MANIFEST_SIZE * 2;
    let completed = 0;
    const advance = (phase) => (length) => {
      completed += length;
      onProgress({ phase, completed, total });
    };

    onProgress({ phase: "erase", completed, total });
    await this.eraseUserImage();
    onProgress({ phase: "write", completed, total });
    await this.writeAt(USER_IMAGE * IMAGE_SLOT_SIZE, bytes, advance("write"));
    await this.writeAt(manifestAddress, manifest.bytes, advance("write"));
    onProgress({ phase: "verify", completed, total });
    await this.verifyAt(USER_IMAGE * IMAGE_SLOT_SIZE, bytes, advance("verify"));
    await this.verifyAt(manifestAddress, manifest.bytes, advance("verify"));

    return manifest;
  }

  async #request(channel, opcode, payload = new Uint8Array()) {
    const sequence = this.#sequence;
    this.#sequence = (this.#sequence + 1) & 0xff;
    const response = await this.#transport.exchange(
      { channel, opcode, sequence, payload },
      this.#timeoutMs,
    );
    return response.payload;
  }
}

export function createUserManifest(data) {
  const bytes = toBytes(data);
  if (bytes.length === 0) {
    throw new Error("image is empty");
  }
  if (bytes.length > MAX_IMAGE_SIZE) {
    throw new Error(`image is ${bytes.length} bytes; slot permits at most ${MAX_IMAGE_SIZE} bytes`);
  }

  const output = new Uint8Array(MANIFEST_SIZE).fill(0xff);
  output.set([0x4e, 0x4d, 0x46, 0x31], 0);
  output[4] = 1;
  output[5] = USER_IMAGE;
  output[6] = 0;
  output[7] = 0;
  const view = new DataView(output.buffer);
  view.setUint32(8, bytes.length, true);
  const checksum = crc32(bytes);
  view.setUint32(12, checksum, true);
  return { image: USER_IMAGE, imageLength: bytes.length, crc32: checksum, bytes: output };
}

function encodeAddress(address) {
  if (!Number.isInteger(address) || address < 0 || address >= 0x1_000000) {
    throw new Error(`invalid 24-bit FLASH address ${address}`);
  }
  return Uint8Array.of(address & 0xff, (address >>> 8) & 0xff, (address >>> 16) & 0xff);
}

function requireFlashRange(address, length) {
  if (
    !Number.isInteger(address) ||
    !Number.isInteger(length) ||
    address < 0 ||
    length < 0 ||
    address + length > FLASH_END
  ) {
    throw new Error(`invalid FLASH range 0x${address.toString(16)} + ${length}`);
  }
}

function requireImage(image) {
  if (!Number.isInteger(image) || image < BOOT_IMAGE || image > USER_IMAGE) {
    throw new Error(`invalid image number ${image}`);
  }
}

function requireLength(payload, expected, operation) {
  if (payload.length !== expected) {
    throw new Error(`${operation} response must be ${expected} bytes, got ${payload.length}`);
  }
}

function checkStatus(status, names, channel) {
  if (status === 0) {
    return;
  }
  const name = names[status] ?? `Unknown status 0x${hexByte(status)}`;
  throw new Error(`${channel} request rejected: ${name}`);
}

function toBytes(value) {
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

function hexByte(value) {
  return value.toString(16).padStart(2, "0");
}
