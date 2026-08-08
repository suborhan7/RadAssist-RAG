// e2e/harness.mjs
// ============================================================================
// Shared orchestration for the E2E scripts (run.mjs, readonly-ownership.mjs).
//
// FAIL CLOSED: E2E_DB must be set explicitly to a disposable path. The harness
// never guesses a DB target, so it can never fall back to dev.db. If E2E_DB is
// unset, or equals the fixture/dev DB, it refuses to run.
// ============================================================================
import { spawn, spawnSync } from "node:child_process";
import { resolve, join } from "node:path";
import { counts, cleanupByIds } from "./db.mjs";

export const REPO = resolve(import.meta.dirname, "..");
export const BACKEND = join(REPO, "backend");
const env = (k, d) => process.env[k] ?? d;
export const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

export function loadConfig() {
  const devDb = resolve(env("E2E_FIXTURE", join(BACKEND, "dev.db")));
  const testDb = process.env.E2E_DB ? resolve(process.env.E2E_DB) : null; // REQUIRED
  return {
    devDb,
    testDb,
    apiBase: env("E2E_API", "http://localhost:8000"),
    frontendBase: env("E2E_FRONTEND", "http://localhost:3000"),
    backendPort: Number(env("E2E_BACKEND_PORT", "8000")),
    cdpPort: Number(env("E2E_CDP_PORT", "9222")),
    python: env("E2E_PYTHON", join(REPO, ".venv", "Scripts", "python.exe")),
    edge: env("E2E_EDGE", "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"),
    image: resolve(env("E2E_IMAGE", join(REPO, "ml/datasets/raw/images/images_normalized/1000_IM-0003-1001.dcm.png"))),
    patientId: env("E2E_PATIENT_ID", "eec21b1214814bae9850354f5f3a5327"),
    outDir: env("E2E_OUT", ""),
  };
}

/** Fail closed. Exits 2 (does not run, does not touch any DB) unless E2E_DB is a safe, explicit target. */
export function assertSafeTarget(cfg) {
  if (!cfg.testDb) {
    console.error(
      "FATAL (fail-closed): E2E_DB is not set. Refusing to run.\n" +
        "  Set E2E_DB to a disposable path, e.g.  E2E_DB=backend/test-e2e.db\n" +
        "  The harness never guesses a DB target, so it can never fall back to dev.db.",
    );
    process.exit(2);
  }
  if (cfg.testDb === cfg.devDb) {
    console.error(`FATAL (fail-closed): E2E_DB (${cfg.testDb}) is the fixture/dev DB. Refusing to run.`);
    process.exit(2);
  }
}

export function killTree(pid) {
  if (!pid) return;
  if (process.platform === "win32") spawnSync("taskkill", ["/PID", String(pid), "/T", "/F"], { stdio: "ignore" });
  else { try { process.kill(-pid, "SIGKILL"); } catch { try { process.kill(pid, "SIGKILL"); } catch {} } }
}

export async function waitHealth(apiBase, timeoutMs) {
  const t0 = Date.now();
  while (Date.now() - t0 < timeoutMs) {
    try { if ((await (await fetch(`${apiBase}/health`)).json()).status === "ok") return true; } catch {}
    await sleep(1500);
  }
  return false;
}

/** Start the backend against the disposable test DB. Throws if it never becomes healthy. */
export async function startBackend(cfg) {
  const proc = spawn(cfg.python, ["-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", String(cfg.backendPort)], {
    cwd: BACKEND,
    env: { ...process.env, PYTHONPATH: REPO, DATABASE_URL: `sqlite:///${cfg.testDb}` },
    stdio: "ignore",
    detached: process.platform !== "win32",
  });
  if (!(await waitHealth(cfg.apiBase, 120000))) { killTree(proc.pid); throw new Error("backend did not become healthy"); }
  return proc;
}

export function launchEdge(cfg) {
  const profile = join(REPO, "e2e", ".edge-profile");
  return spawn(cfg.edge, ["--headless=new", "--disable-gpu", `--remote-debugging-port=${cfg.cdpPort}`, `--user-data-dir=${profile}`, "--hide-scrollbars", "--window-size=1440,900", "about:blank"], { stdio: "ignore" });
}

/**
 * Prove the DATABASE_URL override took effect before the expensive flow: register
 * a throwaway doctor, confirm it landed in test.db and NOT dev.db, then remove it.
 * If it hit dev.db, remove the stray (by id) and throw.
 */
export async function preflightOverride(cfg, devBefore) {
  const pf = await fetch(`${cfg.apiBase}/auth/register`, {
    method: "POST", headers: { "content-type": "application/json" },
    body: JSON.stringify({ email: `e2e-preflight-${Date.now()}@example.test`, password: "e2epass12345", full_name: "E2E preflight" }),
  });
  const pfId = (await pf.json()).doctor?.id;
  const devAfter = counts(cfg.devDb);
  if (devAfter.doctors !== devBefore.doctors) {
    cleanupByIds(cfg.devDb, { doctorId: pfId });
    throw new Error("DB override FAILED: preflight write hit dev.db. Removed the stray; aborting.");
  }
  if (counts(cfg.testDb).doctors !== devBefore.doctors + 1) throw new Error("preflight write did not land in test.db");
  cleanupByIds(cfg.testDb, { doctorId: pfId });
}

/** Minimal CDP page client over the built-in WebSocket. */
export async function cdpConnect(cdpPort) {
  let wsUrl;
  for (let i = 0; i < 30 && !wsUrl; i++) {
    try { wsUrl = (await (await fetch(`http://localhost:${cdpPort}/json`)).json()).find((x) => x.type === "page" && x.webSocketDebuggerUrl)?.webSocketDebuggerUrl; } catch {}
    if (!wsUrl) await sleep(500);
  }
  if (!wsUrl) throw new Error("no CDP page target");
  const ws = new WebSocket(wsUrl);
  await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
  let nextId = 1;
  const pending = new Map();
  ws.onmessage = (ev) => { const m = JSON.parse(ev.data); if (m.id && pending.has(m.id)) { const p = pending.get(m.id); pending.delete(m.id); m.error ? p.reject(new Error(m.error.message)) : p.resolve(m.result); } };
  const send = (method, params = {}) => { const id = nextId++; ws.send(JSON.stringify({ id, method, params })); return new Promise((resolve, reject) => { pending.set(id, { resolve, reject }); setTimeout(() => { if (pending.has(id)) { pending.delete(id); reject(new Error("timeout " + method)); } }, 60000); }); };
  const evalJs = async (expression) => { const r = await send("Runtime.evaluate", { expression, returnByValue: true }); if (r.exceptionDetails) throw new Error(r.exceptionDetails.exception?.description || r.exceptionDetails.text); return r.result.value; };
  return { ws, send, evalJs, close: () => ws.close() };
}
