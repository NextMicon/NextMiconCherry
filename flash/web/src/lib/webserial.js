import { FrameDecoder, encodeFrame, responseOpcode } from "./protocol.js";

export class WebSerialTransport {
  #port;
  #decoder;
  #reader = null;
  #readTask = null;
  #pending = new Map();
  #closing = false;
  #writeQueue = Promise.resolve();
  #onDisconnect;

  constructor(
    port,
    { onProtocolError = () => {}, onDisconnect = () => {} } = {},
  ) {
    this.#port = port;
    this.#onDisconnect = onDisconnect;
    this.#decoder = new FrameDecoder({ onError: onProtocolError });
  }

  async open({ baudRate = 115_200, bufferSize = 4096 } = {}) {
    if (!this.#port.readable || !this.#port.writable) {
      await this.#port.open({ baudRate, bufferSize });
    }
    if (!this.#port.readable || !this.#port.writable) {
      throw new Error("serial port did not provide readable and writable streams");
    }
    this.#closing = false;
    this.#decoder.reset();
    this.#readTask = this.#readLoop();
  }

  async exchange(frame, timeoutMs = 30_000) {
    if (!this.#port.writable || this.#closing) {
      throw new Error("serial port is not open");
    }
    const key = responseKey(frame.channel, responseOpcode(frame.opcode), frame.sequence);
    if (this.#pending.has(key)) {
      throw new Error("a request with the same channel, opcode, and sequence is already pending");
    }

    let timer;
    const response = new Promise((resolve, reject) => {
      timer = setTimeout(() => {
        this.#pending.delete(key);
        reject(new Error(`serial request timed out after ${timeoutMs} ms`));
      }, timeoutMs);
      this.#pending.set(key, { resolve, reject, timer });
    });

    try {
      const wire = encodeFrame(frame);
      const write = this.#writeQueue.then(async () => {
        const writer = this.#port.writable.getWriter();
        try {
          await writer.write(wire);
        } finally {
          writer.releaseLock();
        }
      });
      this.#writeQueue = write.catch(() => {});
      await write;
    } catch (error) {
      const pending = this.#pending.get(key);
      if (pending) {
        clearTimeout(pending.timer);
        this.#pending.delete(key);
        pending.reject(error);
      }
    }

    return response;
  }

  async close() {
    this.#closing = true;
    this.#rejectPending(new Error("serial port closed"));
    if (this.#reader) {
      try {
        await this.#reader.cancel();
      } catch {
        // The device may already have disappeared during warm boot.
      }
    }
    if (this.#readTask) {
      try {
        await this.#readTask;
      } catch {
        // The read loop reports unexpected failures through onDisconnect.
      }
    }
    if (this.#port.readable || this.#port.writable) {
      try {
        await this.#port.close();
      } catch {
        // A physically disconnected port is already closed from the app's perspective.
      }
    }
    this.#readTask = null;
    this.#decoder.reset();
  }

  async #readLoop() {
    let failure = null;
    try {
      while (!this.#closing && this.#port.readable) {
        this.#reader = this.#port.readable.getReader();
        try {
          while (!this.#closing) {
            const { value, done } = await this.#reader.read();
            if (done) {
              break;
            }
            for (const frame of this.#decoder.push(value)) {
              const key = responseKey(frame.channel, frame.opcode, frame.sequence);
              const pending = this.#pending.get(key);
              if (pending) {
                clearTimeout(pending.timer);
                this.#pending.delete(key);
                pending.resolve(frame);
              }
            }
          }
        } finally {
          this.#reader.releaseLock();
          this.#reader = null;
        }
        break;
      }
    } catch (error) {
      failure = error;
    } finally {
      if (!this.#closing) {
        const reason = failure ?? new Error("serial device disconnected");
        this.#rejectPending(reason);
        this.#onDisconnect(reason);
      }
    }
  }

  #rejectPending(error) {
    for (const pending of this.#pending.values()) {
      clearTimeout(pending.timer);
      pending.reject(error);
    }
    this.#pending.clear();
  }
}

function responseKey(channel, opcode, sequence) {
  return `${channel}:${opcode}:${sequence}`;
}
