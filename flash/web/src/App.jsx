import { useCallback, useEffect, useRef, useState } from "react";

import {
  BOOT_IMAGE,
  CAPABILITY_FLASH,
  MAX_IMAGE_SIZE,
  NextMiconClient,
  USER_IMAGE,
  createUserManifest,
} from "./lib/client.js";
import { WebSerialTransport } from "./lib/webserial.js";

const buttonBase =
  "inline-flex min-h-11 items-center justify-center gap-2 rounded-xl px-4 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-40";
const primaryButton = `${buttonBase} bg-mint-600 text-white shadow-lg shadow-mint-600/15 hover:bg-mint-500 dark:bg-mint-400 dark:text-ink-950 dark:hover:bg-mint-300`;
const secondaryButton = `${buttonBase} border border-black/10 bg-white/70 text-ink-900 hover:border-mint-500/60 hover:bg-white dark:border-white/10 dark:bg-white/5 dark:text-white dark:hover:border-mint-400/60 dark:hover:bg-white/10`;
const fieldClass =
  "min-h-11 w-full rounded-xl border border-black/10 bg-white/80 px-3 text-sm text-ink-900 shadow-sm transition hover:border-mint-500/50 disabled:cursor-not-allowed disabled:opacity-50 dark:border-white/10 dark:bg-white/5 dark:text-white";

export default function App() {
  const webSerialAvailable = "serial" in navigator && window.isSecureContext;
  const transportRef = useRef(null);
  const clientRef = useRef(null);
  const portRef = useRef(null);
  const busyRef = useRef(false);
  const logCounterRef = useRef(0);
  const logEndRef = useRef(null);

  const [busy, setBusy] = useState(false);
  const [connection, setConnection] = useState({ label: "未接続", state: "disconnected" });
  const [device, setDevice] = useState(null);
  const [file, setFile] = useState(null);
  const [bootAfter, setBootAfter] = useState(true);
  const [bootSlot, setBootSlot] = useState("0");
  const [progress, setProgress] = useState({ value: 0, label: "待機中" });
  const [logs, setLogs] = useState([]);

  const addLog = useCallback((message, kind = "info") => {
    const time = new Intl.DateTimeFormat("ja-JP", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    }).format(new Date());
    const entry = { id: ++logCounterRef.current, time, message, kind };
    setLogs((current) => [...current.slice(-199), entry]);
  }, []);

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ block: "nearest" });
  }, [logs]);

  const makeTransport = useCallback(
    (port) => {
      let candidate;
      candidate = new WebSerialTransport(port, {
        onProtocolError: (error) =>
          addLog(`不正な受信フレームを破棄しました: ${error.message}`, "warning"),
        onDisconnect: () => {
          if (transportRef.current === candidate) {
            clientRef.current = null;
            setDevice(null);
            setConnection({ label: "切断", state: "disconnected" });
          }
        },
      });
      return candidate;
    },
    [addLog],
  );

  const clearConnection = useCallback(async () => {
    const previous = transportRef.current;
    transportRef.current = null;
    clientRef.current = null;
    portRef.current = null;
    setDevice(null);
    setConnection({ label: "未接続", state: "disconnected" });
    if (previous) {
      await previous.close();
    }
  }, []);

  const installConnection = useCallback((transport, client, port, info) => {
    transportRef.current = transport;
    clientRef.current = client;
    portRef.current = port;
    setDevice({ port, info });
    setConnection({ label: "接続中", state: "connected" });
  }, []);

  const replaceConnection = useCallback(
    async (port) => {
      await clearConnection();
      const candidate = makeTransport(port);
      try {
        await candidate.open();
        const candidateClient = new NextMiconClient(candidate);
        const info = await candidateClient.getInfo();
        installConnection(candidate, candidateClient, port, info);
      } catch (error) {
        await candidate.close();
        throw error;
      }
    },
    [clearConnection, installConnection, makeTransport],
  );

  const reconnectToImage = useCallback(
    async (expectedImage, timeoutMs = 15_000) => {
      const previousPort = portRef.current;
      const identity = usbIdentity(previousPort);
      await clearConnection();
      setConnection({
        label: `${imageRole(expectedImage)}の再列挙を待機中`,
        state: "waiting",
      });

      const deadline = Date.now() + timeoutMs;
      let lastError = null;
      while (Date.now() < deadline) {
        let authorized;
        try {
          authorized = await navigator.serial.getPorts();
        } catch (error) {
          lastError = error;
          await delay(400);
          continue;
        }
        const candidates = [...new Set([previousPort, ...authorized].filter(Boolean))].filter(
          (port) => port === previousPort || sameUsbIdentity(identity, usbIdentity(port)),
        );

        for (const port of candidates) {
          const candidate = makeTransport(port);
          try {
            await candidate.open();
            const candidateClient = new NextMiconClient(candidate);
            const info = await candidateClient.getInfo();
            if (info.activeImage !== expectedImage) {
              lastError = new Error(`${imageRole(info.activeImage)}が応答しました`);
              await candidate.close();
              continue;
            }
            installConnection(candidate, candidateClient, port, info);
            return;
          } catch (error) {
            lastError = error;
            await candidate.close();
          }
        }
        await delay(400);
      }

      setConnection({ label: "再接続が必要", state: "disconnected" });
      const detail = lastError ? `（最後のエラー: ${errorMessage(lastError)}）` : "";
      throw new Error(
        `15秒以内に${imageRole(expectedImage)}へ再接続できませんでした${detail}。「デバイスを選択」で再接続してください`,
      );
    },
    [clearConnection, installConnection, makeTransport],
  );

  const runExclusive = useCallback(
    async (operation) => {
      if (busyRef.current) {
        return;
      }
      busyRef.current = true;
      setBusy(true);
      try {
        await operation();
      } catch (error) {
        addLog(errorMessage(error), "error");
        setProgress({ value: 0, label: "処理を完了できませんでした" });
      } finally {
        busyRef.current = false;
        setBusy(false);
      }
    },
    [addLog],
  );

  useEffect(() => {
    if (!("serial" in navigator)) {
      return undefined;
    }
    const handleDisconnect = (event) => {
      if (event.target === portRef.current && !busyRef.current) {
        clientRef.current = null;
        setDevice(null);
        setConnection({ label: "切断", state: "disconnected" });
      }
    };
    navigator.serial.addEventListener("disconnect", handleDisconnect);
    return () => {
      navigator.serial.removeEventListener("disconnect", handleDisconnect);
      const current = transportRef.current;
      transportRef.current = null;
      clientRef.current = null;
      portRef.current = null;
      void current?.close();
    };
  }, []);

  const handleConnect = () =>
    runExclusive(async () => {
      const port = await navigator.serial.requestPort();
      await replaceConnection(port);
      addLog("デバイスへ接続しました。", "success");
    });

  const handleDisconnect = () =>
    runExclusive(async () => {
      await clearConnection();
      addLog("接続を解除しました。");
    });

  const handleFlash = () =>
    runExclusive(async () => {
      let activeClient = requireClient(clientRef.current);
      if (!file) {
        throw new Error("書き込むbitstreamを選択してください");
      }
      const bytes = new Uint8Array(await file.arrayBuffer());
      const expectedManifest = createUserManifest(bytes);

      addLog(`userへ${formatBytes(bytes.length)}を書き込みます。`);
      const initialInfo = await activeClient.getInfo();
      if (initialInfo.activeImage !== BOOT_IMAGE) {
        addLog(
          `FLASH機能を使うため${imageRole(initialInfo.activeImage)}からbootへ切り替えます。`,
        );
        await activeClient.selectImage(BOOT_IMAGE);
        await reconnectToImage(BOOT_IMAGE);
        activeClient = requireClient(clientRef.current);
      }

      const info = await activeClient.getInfo();
      setDevice({ port: portRef.current, info });
      if ((info.capabilities & CAPABILITY_FLASH) === 0) {
        throw new Error("接続中のイメージはFLASH機能を提供していません");
      }

      setProgress({ value: 0, label: "user領域を消去しています…" });
      const manifest = await activeClient.programUserImage(
        bytes,
        ({ phase, completed, total }) => {
          const labels = { erase: "消去中", write: "書き込み中", verify: "検証中" };
          setProgress({
            value: total === 0 ? 0 : completed / total,
            label: `${labels[phase]} — ${formatBytes(completed)} / ${formatBytes(total)}`,
          });
        },
      );
      setProgress({ value: 1, label: "書き込みとreadback検証が完了しました" });
      if (manifest.crc32 !== expectedManifest.crc32) {
        throw new Error("内部マニフェスト検証に失敗しました");
      }
      addLog(
        `userを書き込み、検証しました（CRC32 ${hex32(manifest.crc32)}）。`,
        "success",
      );

      if (bootAfter) {
        addLog("userを起動します。");
        await activeClient.selectImage(USER_IMAGE);
        try {
          await reconnectToImage(USER_IMAGE);
          addLog("userで再接続しました。", "success");
        } catch (error) {
          addLog(
            `書き込みは完了しましたが、自動再接続できませんでした: ${errorMessage(error)}`,
            "warning",
          );
        }
      }
    });

  const handleBoot = () =>
    runExclusive(async () => {
      const activeClient = requireClient(clientRef.current);
      const image = Number(bootSlot);
      addLog(`${imageRole(image)}への切り替えを要求します。`);
      await activeClient.selectImage(image);
      await reconnectToImage(image);
      addLog(`${imageRole(image)}で再接続しました。`, "success");
    });

  const connected = device !== null;
  const invalidFile = file && (file.size === 0 || file.size > MAX_IMAGE_SIZE);

  return (
    <div className="relative min-h-screen overflow-hidden">
      <div className="pointer-events-none absolute top-0 left-1/2 -z-10 h-[38rem] w-[70rem] -translate-x-1/2 rounded-full bg-mint-300/10 blur-3xl" />
      <main className="mx-auto w-full max-w-5xl px-4 py-10 sm:px-6 sm:py-16">
        <header className="mb-10 flex flex-col gap-8 sm:mb-14 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <div className="mb-5 flex items-center gap-3">
              <span className="grid size-9 place-items-center rounded-xl bg-ink-950 text-sm font-black text-mint-300 shadow-lg shadow-black/15 dark:bg-mint-400 dark:text-ink-950">
                NM
              </span>
              <span className="text-xs font-bold tracking-[0.18em] text-ink-700 uppercase dark:text-white/55">
                NextMicon Cherry
              </span>
            </div>
            <h1 className="max-w-3xl text-4xl leading-[0.95] font-semibold tracking-[-0.055em] text-ink-950 sm:text-6xl dark:text-white">
              Web Flasher
            </h1>
            <p className="mt-5 max-w-2xl text-sm leading-6 text-ink-700 sm:text-base dark:text-white/60">
              Rust WASMのCOBS・CRC32実装を使い、bitstreamをブラウザ内だけで安全に処理します。
            </p>
          </div>
          <div className="flex shrink-0 items-center gap-2 rounded-full border border-mint-600/15 bg-mint-100/60 px-3 py-1.5 text-xs font-semibold text-mint-600 dark:border-mint-400/20 dark:bg-mint-400/10 dark:text-mint-300">
            <span className="size-1.5 rounded-full bg-mint-500" />
            React · Tailwind · Rust WASM
          </div>
        </header>

        {!webSerialAvailable && (
          <div className="mb-5 rounded-2xl border border-red-300 bg-red-50 p-4 text-sm leading-6 text-red-900 dark:border-red-900 dark:bg-red-950/60 dark:text-red-100">
            Web Serialを利用できません。対応するChromium系ブラウザでlocalhostまたはHTTPSから開いてください。
          </div>
        )}

        <div className="grid gap-5 lg:grid-cols-[1.1fr_0.9fr]">
          <div className="space-y-5">
            <Card>
              <StepHeader number="01" title="デバイス" aside={<StatusBadge {...connection} />} />
              <div className="rounded-2xl border border-black/5 bg-black/[0.025] p-4 dark:border-white/5 dark:bg-white/[0.025]">
                <p className="text-xs font-semibold tracking-wide text-ink-700 uppercase dark:text-white/45">
                  Active connection
                </p>
                <p className="mt-2 min-h-5 font-mono text-sm text-ink-900 dark:text-white/85">
                  {deviceDescription(device)}
                </p>
              </div>
              <div className="mt-4 flex flex-col gap-2 sm:flex-row">
                <button
                  className={`${primaryButton} sm:flex-1`}
                  type="button"
                  disabled={busy || !webSerialAvailable}
                  onClick={handleConnect}
                >
                  <UsbIcon />
                  デバイスを選択
                </button>
                <button
                  className={secondaryButton}
                  type="button"
                  disabled={busy || !connected}
                  onClick={handleDisconnect}
                >
                  接続解除
                </button>
              </div>
            </Card>

            <Card>
              <StepHeader number="02" title="書き込み" />
              <div>
                <label className="block text-sm font-semibold text-ink-700 dark:text-white/65">
                  Bitstream
                  <input
                    className={`${fieldClass} mt-2 file:mr-3 file:border-0 file:bg-transparent file:text-sm file:font-bold file:text-mint-600 dark:file:text-mint-300`}
                    type="file"
                    accept=".bin,application/octet-stream"
                    disabled={busy}
                    onChange={(event) => setFile(event.target.files?.[0] ?? null)}
                  />
                  <span
                    className={`mt-2 block text-xs font-normal ${invalidFile ? "text-red-600 dark:text-red-300" : "text-ink-700/70 dark:text-white/40"}`}
                  >
                    {fileDescription(file)}
                  </span>
                </label>
              </div>

              <label className="mt-5 flex cursor-pointer items-center gap-3 text-sm text-ink-800 dark:text-white/75">
                <input
                  className="size-4 accent-mint-600"
                  type="checkbox"
                  checked={bootAfter}
                  disabled={busy}
                  onChange={(event) => setBootAfter(event.target.checked)}
                />
                検証後にこのイメージを起動する
              </label>

              <button
                className={`${primaryButton} mt-5 w-full`}
                type="button"
                disabled={busy || !connected || !file || invalidFile}
                onClick={handleFlash}
              >
                <FlashIcon />
                消去・書き込み・検証
              </button>

              <div className="mt-5" aria-live="polite">
                <div className="h-2 overflow-hidden rounded-full bg-black/8 dark:bg-white/10">
                  <div
                    className="h-full rounded-full bg-mint-500 transition-[width] duration-200"
                    style={{ width: `${Math.max(0, Math.min(1, progress.value)) * 100}%` }}
                  />
                </div>
                <p className="mt-2 text-xs text-ink-700/75 dark:text-white/45">{progress.label}</p>
              </div>
            </Card>
          </div>

          <div className="space-y-5">
            <Card>
              <StepHeader number="03" title="イメージ切り替え" />
              <label className="block text-sm font-semibold text-ink-700 dark:text-white/65">
                起動先
                <select
                  className={`${fieldClass} mt-2`}
                  value={bootSlot}
                  disabled={busy}
                  onChange={(event) => setBootSlot(event.target.value)}
                >
                  <option value={BOOT_IMAGE}>boot — recovery</option>
                  <option value={USER_IMAGE}>user</option>
                </select>
              </label>
              <button
                className={`${secondaryButton} mt-4 w-full`}
                type="button"
                disabled={busy || !connected}
                onClick={handleBoot}
              >
                切り替えて再接続
              </button>
            </Card>

            <Card className="min-h-[22rem]">
              <StepHeader
                number="LOG"
                title="処理ログ"
                aside={
                  logs.length > 0 ? (
                    <button
                      className="text-xs font-semibold text-ink-700/60 hover:text-mint-600 dark:text-white/35 dark:hover:text-mint-300"
                      type="button"
                      onClick={() => setLogs([])}
                    >
                      クリア
                    </button>
                  ) : null
                }
              />
              <div
                className="h-64 overflow-y-auto rounded-2xl bg-ink-950 p-4 font-mono text-xs leading-6 text-white/65 shadow-inner"
                role="log"
                aria-live="polite"
              >
                {logs.length === 0 ? (
                  <p className="text-white/30">接続すると処理内容がここに表示されます。</p>
                ) : (
                  logs.map((entry) => (
                    <p className={logColor(entry.kind)} key={entry.id}>
                      <span className="mr-3 text-white/25">{entry.time}</span>
                      {entry.message}
                    </p>
                  ))
                )}
                <span ref={logEndRef} />
              </div>
            </Card>
          </div>
        </div>

        <footer className="mt-8 flex flex-col gap-2 px-1 text-xs leading-5 text-ink-700/60 sm:flex-row sm:items-center sm:justify-between dark:text-white/35">
          <p>bootはUSB経由で書き換えできません。復旧には外部SPIヘッダーを使用します。</p>
          <p className="font-mono">NMF1 · protocol v1</p>
        </footer>
      </main>
    </div>
  );
}

function Card({ children, className = "" }) {
  return (
    <section
      className={`rounded-3xl border border-white/70 bg-white/72 p-5 shadow-[0_18px_60px_rgba(16,32,25,0.08)] backdrop-blur-xl sm:p-6 dark:border-white/8 dark:bg-white/[0.055] dark:shadow-black/20 ${className}`}
    >
      {children}
    </section>
  );
}

function StepHeader({ number, title, aside = null }) {
  return (
    <div className="mb-5 flex items-center justify-between gap-4">
      <div>
        <p className="text-[0.68rem] font-black tracking-[0.2em] text-mint-600 uppercase dark:text-mint-300">
          {number}
        </p>
        <h2 className="mt-1 text-lg font-semibold tracking-tight text-ink-950 dark:text-white">
          {title}
        </h2>
      </div>
      {aside}
    </div>
  );
}

function StatusBadge({ label, state }) {
  const colors = {
    connected: "bg-mint-100 text-mint-600 dark:bg-mint-400/10 dark:text-mint-300",
    waiting: "bg-amber-100 text-amber-800 dark:bg-amber-400/10 dark:text-amber-200",
    disconnected: "bg-black/5 text-ink-700/70 dark:bg-white/8 dark:text-white/45",
  };
  return (
    <span className={`rounded-full px-3 py-1.5 text-xs font-semibold ${colors[state]}`}>
      {label}
    </span>
  );
}

function UsbIcon() {
  return (
    <svg aria-hidden="true" className="size-4" viewBox="0 0 24 24" fill="none">
      <path d="M12 3v12m0-12-2.5 2.5M12 3l2.5 2.5M12 10l-4-2.5v7M12 13l4-2.5v3" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx="8" cy="17" r="2" stroke="currentColor" strokeWidth="1.8" />
      <rect x="14.5" y="13.5" width="3" height="3" rx="0.5" stroke="currentColor" strokeWidth="1.5" />
      <path d="M12 15v3.5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}

function FlashIcon() {
  return (
    <svg aria-hidden="true" className="size-4" viewBox="0 0 24 24" fill="none">
      <path d="M13.5 2 5 13h6l-.5 9L19 11h-6l.5-9Z" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" />
    </svg>
  );
}

function requireClient(client) {
  if (!client) {
    throw new Error("先にNextMiconデバイスへ接続してください");
  }
  return client;
}

function usbIdentity(port) {
  return port?.getInfo?.() ?? {};
}

function sameUsbIdentity(left, right) {
  if (left.usbVendorId === undefined || left.usbProductId === undefined) {
    return false;
  }
  return left.usbVendorId === right.usbVendorId && left.usbProductId === right.usbProductId;
}

function deviceDescription(device) {
  if (!device) {
    return "—";
  }
  const { usbVendorId, usbProductId } = usbIdentity(device.port);
  const usb =
    usbVendorId === undefined || usbProductId === undefined
      ? "USB ID 不明"
      : `${hex16(usbVendorId)}:${hex16(usbProductId)}`;
  return `${usb} · ${imageRole(device.info.activeImage)} · caps 0x${device.info.capabilities.toString(16).padStart(2, "0")}`;
}

function imageRole(image) {
  return image === BOOT_IMAGE ? "boot" : image === USER_IMAGE ? "user" : `invalid image ${image}`;
}

function fileDescription(file) {
  if (!file) {
    return "最大262,112 bytesの.binファイル";
  }
  const suffix = file.size > MAX_IMAGE_SIZE ? "（最大サイズ超過）" : "";
  return `${file.name} — ${formatBytes(file.size)}${suffix}`;
}

function logColor(kind) {
  return {
    error: "text-red-300",
    warning: "text-amber-200",
    success: "text-mint-300",
    info: "text-white/65",
  }[kind];
}

function errorMessage(error) {
  return error instanceof Error ? error.message : String(error);
}

function delay(milliseconds) {
  return new Promise((resolve) => setTimeout(resolve, milliseconds));
}

function formatBytes(value) {
  return `${new Intl.NumberFormat("ja-JP").format(value)} bytes`;
}

function hex16(value) {
  return value.toString(16).padStart(4, "0");
}

function hex32(value) {
  return value.toString(16).padStart(8, "0");
}
