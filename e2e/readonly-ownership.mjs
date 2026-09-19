// e2e/readonly-ownership.mjs
// ============================================================================
// Task 4: demonstrate the frozen ownership model, on the disposable-DB harness.
//
// Doctor A produces + finalizes a report. Doctor B then:
//   - opens A's report in the UI  -> read-only (no edit/regenerate/finalize/
//     restore; ownership chip is another doctor, not "You")
//   - can read the institutional patient + that patient's history (200)
//   - is REJECTED by the API on every write, bypassing the UI entirely:
//       PATCH /reports/{id}                 -> 403
//       PATCH /reports/{id}/finalize        -> 403
//       POST  /reports/{id}/regenerate-section -> 403
//       DELETE /reports/{id}                  -> 403  (and the report survives)
//       GET   /reports/{id}                 -> 200
//   - leaves the report's updated_at unchanged (a 403 that still mutated would
//     be worse than a 200).
//
// A hidden button is UI; the 403 is the guarantee. Cleanup is ID-scoped;
// dev.db is never opened. Fails closed if E2E_DB is unset.
// ============================================================================
import { existsSync, rmSync } from "node:fs";
import { join } from "node:path";
import { DatabaseSync } from "node:sqlite";
import { counts, copyFixture, recordDerivedIds, cleanupByIds, dropDb, dbId } from "./db.mjs";
import { runOwnerFlow } from "./owner-flow.mjs";
import { loadConfig, assertSafeTarget, killTree, startBackend, launchEdge, preflightOverride, cdpConnect, sleep, BACKEND } from "./harness.mjs";

const cfg = loadConfig();
assertSafeTarget(cfg);
const log = (...a) => console.log(...a);

let backend, edge;
async function teardown() { killTree(backend?.pid); killTree(edge?.pid); await sleep(1500); }

async function registerDoctor(label) {
  const res = await fetch(`${cfg.apiBase}/auth/register`, {
    method: "POST", headers: { "content-type": "application/json" },
    body: JSON.stringify({ email: `e2e-${label}-${Date.now()}@example.test`, password: "e2epass12345", full_name: `E2E ${label} (disposable)` }),
  });
  const body = await res.json();
  const jwt = (res.headers.getSetCookie?.() ?? []).find((c) => c.startsWith("radassist_token="))?.split(";")[0].split("=")[1];
  return { doctorId: body.doctor?.id ?? body.id, jwt };
}

async function apiAs(jwt, method, path, body) {
  const res = await fetch(`${cfg.apiBase}${path}`, {
    method,
    headers: { Cookie: `radassist_token=${jwt}`, ...(body ? { "content-type": "application/json" } : {}) },
    body: body ? JSON.stringify(body) : undefined,
  });
  const txt = await res.text();
  let parsed; try { parsed = JSON.parse(txt); } catch { parsed = txt; }
  return { status: res.status, body: parsed };
}

function readUpdatedAt(reportId) {
  const db = new DatabaseSync(cfg.testDb, { readOnly: true });
  const r = db.prepare("SELECT updated_at FROM reports WHERE id = ?").get(dbId(reportId));
  db.close();
  return r?.updated_at ?? null;
}

async function main() {
  const devBefore = counts(cfg.devDb);
  log(`dev.db BEFORE: ${JSON.stringify(devBefore)}`);

  dropDb(cfg.testDb);
  copyFixture(cfg.devDb, cfg.testDb);
  backend = await startBackend(cfg);
  await preflightOverride(cfg, devBefore);
  log("backend healthy; DB override confirmed (dev.db untouched)");

  // --- Doctor A: produce + finalize a report --------------------------------
  edge = launchEdge(cfg);
  await sleep(3000);
  log("\n=== Doctor A: produce + finalize a report ===");
  const a = await runOwnerFlow(cfg);
  const reportId = a.createdIds.reportId;
  if (a.results.steps.finalize !== "PASS" || !reportId) throw new Error("doctor A did not finalize a report");
  log(`  A finalized report ${reportId} (steps: ${JSON.stringify(a.results.steps)})`);

  // --- Doctor B --------------------------------------------------------------
  const b = await registerDoctor("B");
  log(`\n=== Doctor B registered: ${b.doctorId} ===`);

  // --- B opens A's report in the UI -> read-only ----------------------------
  const cdp = await cdpConnect(cfg.cdpPort);
  await cdp.send("Page.enable"); await cdp.send("Network.enable");
  await cdp.send("Emulation.setDeviceMetricsOverride", { width: 1440, height: 900, deviceScaleFactor: 1, mobile: false });
  await cdp.send("Network.setCookie", { name: "radassist_token", value: b.jwt, domain: "localhost", path: "/", httpOnly: true, secure: false, sameSite: "Lax" });
  await cdp.send("Page.navigate", { url: `${cfg.frontendBase}/reports/${reportId}` });
  await sleep(5000);
  const shotPath = cfg.outDir ? `${cfg.outDir}/readonly-B-view.png` : null;
  if (shotPath) {
    const { data } = await cdp.send("Page.captureScreenshot", { format: "png", clip: { x: 0, y: 0, width: 1440, height: 900, scale: 1 } });
    (await import("node:fs")).writeFileSync(shotPath, Buffer.from(data, "base64"));
  }
  const ui = JSON.parse(await cdp.evalJs(`JSON.stringify({
    finalizeBtn: [...document.querySelectorAll('button')].some(b=>b.textContent.trim()==='Finalize'),
    editBtn: [...document.querySelectorAll('button')].some(b=>b.textContent.trim()==='Edit'),
    regenerateBtn: [...document.querySelectorAll('button')].some(b=>b.textContent.trim()==='Regenerate'),
    restore: /Restore draft/.test(document.body.innerText),
    belongsToBanner: /belongs to/.test(document.body.innerText),
    ownerChipSaysYou: [...document.querySelectorAll('span')].some(s=>s.textContent.trim()==='You'),
  })`));
  cdp.close();
  log(`\n=== B's UI view of A's report (screenshot: ${shotPath ?? "n/a"}) ===`);
  log(`  ${JSON.stringify(ui)}`);

  // --- B can read the institutional patient + history -----------------------
  const patient = await apiAs(b.jwt, "GET", `/patients/${cfg.patientId}`);
  const history = await apiAs(b.jwt, "GET", `/patients/${cfg.patientId}/history`);
  log(`\n=== B reads institutional patient + history ===`);
  log(`  GET /patients/{id}          -> ${patient.status} (${patient.body?.patient_code ?? "?"})`);
  log(`  GET /patients/{id}/history  -> ${history.status} (${Array.isArray(history.body) ? history.body.length : "?"} studies)`);

  // --- B hits the API directly (bypassing the UI) ---------------------------
  const beforeUpdatedAt = readUpdatedAt(reportId);
  const patch = await apiAs(b.jwt, "PATCH", `/reports/${reportId}`, { findings: "OWNERSHIP TEST - this write must be rejected" });
  const finalize = await apiAs(b.jwt, "PATCH", `/reports/${reportId}/finalize`);
  const regen = await apiAs(b.jwt, "POST", `/reports/${reportId}/regenerate-section`, { field: "findings" });
  // DELETE is the newest write and the only irreversible one, so it is the one
  // a missing ownership check would cost the most. B must be refused it exactly
  // like every other write -- and the report must still be there afterwards,
  // which the reportStillExists check below proves independently of the status
  // code (a 403 that deleted anyway would still read as "rejected" here).
  const del = await apiAs(b.jwt, "DELETE", `/reports/${reportId}`);
  const get = await apiAs(b.jwt, "GET", `/reports/${reportId}`);
  const afterUpdatedAt = readUpdatedAt(reportId);
  const reportStillExists = get.status === 200;

  log(`\n=== B's direct API calls on A's report ===`);
  log(`  PATCH  /reports/{id}                  -> ${patch.status}  ${JSON.stringify(patch.body)}`);
  log(`  PATCH  /reports/{id}/finalize         -> ${finalize.status}  ${JSON.stringify(finalize.body)}`);
  log(`  POST   /reports/{id}/regenerate-section -> ${regen.status}  ${JSON.stringify(regen.body)}`);
  log(`  DELETE /reports/{id}                  -> ${del.status}  ${JSON.stringify(del.body)}`);
  log(`  GET    /reports/{id}                  -> ${get.status}  (read permitted)`);
  log(`  report still exists after DELETE      -> ${reportStillExists}`);
  log(`\n=== updated_at unchanged after rejected writes ===`);
  log(`  before: ${beforeUpdatedAt}`);
  log(`  after : ${afterUpdatedAt}`);

  // --- Verdict ---------------------------------------------------------------
  const writesRejected =
    patch.status === 403 && finalize.status === 403 && regen.status === 403 && del.status === 403;
  const readOk = get.status === 200 && patient.status === 200 && history.status === 200;
  const uiReadOnly = !ui.finalizeBtn && !ui.editBtn && !ui.regenerateBtn && !ui.restore && ui.belongsToBanner && !ui.ownerChipSaysYou;
  const stateIntact = beforeUpdatedAt === afterUpdatedAt && reportStillExists;
  const anyWriteAccepted = [patch, finalize, regen, del].some((r) => r.status < 300);
  if (anyWriteAccepted) log("\n!!! SECURITY FAILURE: a non-owner write was ACCEPTED !!!");

  // --- Cleanup (ID-scoped): A's recorded set + B's doctor row ---------------
  await teardown();
  recordDerivedIds(cfg.testDb, a.createdIds);
  for (const p of a.createdIds.imagePaths ?? []) for (const c of [p, join(BACKEND, p)]) if (c && existsSync(c)) { rmSync(c, { force: true }); break; }
  const delA = cleanupByIds(cfg.testDb, a.createdIds);
  const delB = cleanupByIds(cfg.testDb, { doctorId: b.doctorId });
  log(`\n=== ID-scoped cleanup ===\n  A: ${JSON.stringify(delA)}\n  B: ${JSON.stringify(delB)}`);
  dropDb(cfg.testDb);

  const devAfter = counts(cfg.devDb);
  const devUnchanged = JSON.stringify(devAfter) === JSON.stringify(devBefore);
  log(`\n=== dev.db AFTER: ${JSON.stringify(devAfter)}  UNCHANGED: ${devUnchanged ? "YES ✓" : "NO !!!"} ===`);

  const pass = writesRejected && readOk && uiReadOnly && stateIntact && devUnchanged && !anyWriteAccepted;
  log(`\n=== VERDICT: ${pass ? "PASS ✓" : "FAIL"} ===`);
  log(`  writes 403: ${writesRejected} | reads 200: ${readOk} | UI read-only: ${uiReadOnly} | updated_at intact: ${stateIntact} | dev unchanged: ${devUnchanged}`);
  process.exit(pass ? 0 : 1);
}

main().catch(async (e) => { console.error("FATAL:", e.message); await teardown(); dropDb(cfg.testDb); process.exit(1); });
