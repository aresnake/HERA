#!/usr/bin/env node
"use strict";

const { setTimeout: delay } = require("timers/promises");

const url = process.env.MCP_SOCKET_URL;
if (!url) {
  console.error("MCP_SOCKET_URL is required.");
  process.exit(1);
}

const args = process.argv.slice(2);
const pingMode = args.includes("--ping");

let shuttingDown = false;
let ws = null;
let backoffMs = 250;
const maxBackoffMs = 5000;

function logError(msg) {
  console.error(msg);
}

function resetBackoff() {
  backoffMs = 250;
}

async function connectOnce() {
  return new Promise((resolve, reject) => {
    let settled = false;
    ws = new WebSocket(url);

    ws.addEventListener("open", () => {
      if (settled) return;
      settled = true;
      resolve(ws);
    });

    ws.addEventListener("error", (err) => {
      if (settled) {
        logError(`WebSocket error: ${err && err.message ? err.message : err}`);
        return;
      }
      settled = true;
      reject(err);
    });

    ws.addEventListener("close", () => {
      if (!settled) {
        settled = true;
        reject(new Error("WebSocket closed before open."));
      }
    });
  });
}

async function connectWithBackoff() {
  while (!shuttingDown) {
    try {
      const socket = await connectOnce();
      resetBackoff();
      return socket;
    } catch (err) {
      logError(`WebSocket connect failed, retrying in ${backoffMs}ms.`);
      await delay(backoffMs);
      backoffMs = Math.min(maxBackoffMs, backoffMs * 2);
    }
  }
  throw new Error("Shutting down.");
}

function setupSocketHandlers(socket) {
  socket.addEventListener("message", (event) => {
    if (shuttingDown) return;
    const data =
      typeof event.data === "string" ? event.data : event.data.toString();
    process.stdout.write(data);
    if (!data.endsWith("\n")) process.stdout.write("\n");
  });

  socket.addEventListener("error", (err) => {
    if (shuttingDown) return;
    logError(`WebSocket error: ${err && err.message ? err.message : err}`);
  });
}

/**
 * Convert stdin JSON lines into the typed envelope expected by the HERA WS server.
 *
 * Accepted input forms:
 * 1) { "type": "tools/list" }                       -> passthrough
 * 2) JSON-RPC { "jsonrpc":"2.0","method":"tools/list" ... } -> mapped to {type:"tools/list"}
 * 3) JSON-RPC { "jsonrpc":"2.0","method":"tools/call","params":{...} } -> {type:"tools/call", ...params}
 *
 * Any other payload is rejected locally (prints {ok:false,...} to stdout).
 */
function normalizeOutbound(line) {
  const trimmed = line.trim();
  if (!trimmed) return null;

  let obj;
  try {
    obj = JSON.parse(trimmed);
  } catch {
    process.stdout.write(
      JSON.stringify({
        ok: false,
        error: {
          code: "invalid_json",
          message: "Input must be JSON (either {type:...} or JSON-RPC tools/*).",
        },
      }) + "\n"
    );
    return null;
  }

  if (!obj || typeof obj !== "object") {
    process.stdout.write(
      JSON.stringify({
        ok: false,
        error: {
          code: "unsupported_payload",
          message: "Payload must be a JSON object.",
        },
      }) + "\n"
    );
    return null;
  }

  // Already in server envelope form
  if (typeof obj.type === "string" && obj.type.length) {
    // Compatibility: some servers expect "args" instead of "arguments" for tools/call
    if (obj.type === "tools/call" && obj && typeof obj === "object") {
      if (obj.arguments && typeof obj.arguments === "object" && !obj.args) obj.args = obj.arguments;
      if (obj.args && typeof obj.args === "object" && !obj.arguments) obj.arguments = obj.args;
    }
    return JSON.stringify(obj);
  }

  // JSON-RPC mapping (tools/* only)
  if (typeof obj.jsonrpc === "string" && obj.jsonrpc.length && typeof obj.method === "string") {
    const method = obj.method;
    const params =
      obj.params && typeof obj.params === "object" ? obj.params : {};

    if (method === "tools/list") {
      return JSON.stringify({ type: "tools/list" });
    }

    if (method === "tools/call") {
      // Forward as typed envelope; keep both "arguments" and "args" for compatibility
      // Expected params commonly: { name: "tool.name", arguments: {...} }
      const out = { type: "tools/call", ...params };
      if (out.arguments && typeof out.arguments === "object" && !out.args) out.args = out.arguments;
      if (out.args && typeof out.args === "object" && !out.arguments) out.arguments = out.args;
      return JSON.stringify(out);
    }

    process.stdout.write(
      JSON.stringify({
        ok: false,
        error: {
          code: "unsupported_method",
          message:
            `Proxy only supports JSON-RPC methods tools/list and tools/call (got: ${method})`,
        },
      }) + "\n"
    );
    return null;
  }

  // Unknown JSON shape: reject locally (avoid sending garbage types to server)
  process.stdout.write(
    JSON.stringify({
      ok: false,
      error: {
        code: "unsupported_payload",
        message: "Payload must be {type:...} or JSON-RPC tools/list|tools/call.",
      },
    }) + "\n"
  );
  return null;
}

async function runPing() {
  const socket = await connectWithBackoff();

  return new Promise((resolve, reject) => {
    const onMessage = (event) => {
      const data =
        typeof event.data === "string" ? event.data : event.data.toString();
      process.stdout.write(data);
      if (!data.endsWith("\n")) process.stdout.write("\n");
      cleanup();
      resolve();
    };

    const onClose = () => {
      cleanup();
      reject(new Error("WebSocket closed before ping response."));
    };

    const onError = (err) => {
      cleanup();
      reject(err);
    };

    function cleanup() {
      socket.removeEventListener("message", onMessage);
      socket.removeEventListener("close", onClose);
      socket.removeEventListener("error", onError);
      try {
        socket.close();
      } catch {}
    }

    socket.addEventListener("message", onMessage);
    socket.addEventListener("close", onClose);
    socket.addEventListener("error", onError);

    socket.send(JSON.stringify({ type: "tools/list" }));
  });
}

async function pumpStdio() {
  process.stdin.on("error", (err) => {
    logError(`stdin error: ${err && err.message ? err.message : err}`);
  });

  process.stdout.on("error", (err) => {
    logError(`stdout error: ${err && err.message ? err.message : err}`);
  });

  // Newline framing
  let buffer = "";

  while (!shuttingDown) {
    const socket = await connectWithBackoff();
    setupSocketHandlers(socket);

    const onData = (chunk) => {
      if (shuttingDown || socket.readyState !== WebSocket.OPEN) return;

      buffer += chunk.toString("utf8");
      const parts = buffer.split(/\r?\n/);
      buffer = parts.pop() ?? "";

      for (const line of parts) {
        const payload = normalizeOutbound(line);
        if (!payload) continue;
        socket.send(payload);
      }
    };

    const onClose = () => {
      process.stdin.removeListener("data", onData);
    };

    process.stdin.on("data", onData);
    socket.addEventListener("close", onClose, { once: true });

    await new Promise((resolve) =>
      socket.addEventListener("close", resolve, { once: true })
    );
  }
}

function shutdown() {
  if (shuttingDown) return;
  shuttingDown = true;
  try {
    if (ws && ws.readyState === WebSocket.OPEN) ws.close();
  } catch {}
}

process.on("SIGINT", shutdown);
process.on("SIGTERM", shutdown);

(async () => {
  try {
    if (pingMode) {
      await runPing();
      process.exit(0);
    } else {
      await pumpStdio();
    }
  } catch (err) {
    logError(err && err.message ? err.message : String(err));
    process.exit(1);
  }
})();
