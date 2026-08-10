import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import App from "./App.jsx";
import "./index.css";
import { initProtocolWasm } from "./lib/protocol.js";

const root = createRoot(document.getElementById("root"));

try {
  await initProtocolWasm();
  root.render(
    <StrictMode>
      <App />
    </StrictMode>,
  );
} catch (error) {
  root.render(
    <main className="mx-auto flex min-h-screen max-w-xl items-center px-6">
      <section className="rounded-3xl border border-red-300 bg-red-50 p-8 text-red-950 shadow-xl dark:border-red-900 dark:bg-red-950 dark:text-red-100">
        <p className="text-xs font-bold tracking-[0.18em] uppercase">Initialization failed</p>
        <h1 className="mt-3 text-2xl font-semibold">Rust WASMを読み込めませんでした</h1>
        <p className="mt-3 text-sm leading-6 opacity-80">
          {error instanceof Error ? error.message : String(error)}
        </p>
      </section>
    </main>,
  );
}
