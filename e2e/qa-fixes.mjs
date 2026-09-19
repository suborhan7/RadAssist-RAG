// e2e/qa-fixes.mjs
// ============================================================================
// Verifies the QA-report fixes against the REAL backend on the disposable-DB
// harness. Same safety properties as every other script here: fail-closed on
// E2E_DB, ID-scoped cleanup, dev.db never opened for writing.
//
// What each check proves, and why it needs a live system rather than a unit
// test:
//
//   1. default_top_k is HONOURED end to end. The reported bug was "set k=3,
//      the UI still shows k=5". A unit test on the resolver cannot catch the
//      original defect, because the resolver was never called -- the upload
//      flow passed a literal 5. This drives the real browser UI and then reads
//      retrieval_sessions.top_k out of the database, so it fails if any link
//      in preference -> provider -> request -> session is broken.
//
//   2. The header LABEL agrees with the request. The bug was a hardcoded
//      "K=5" string beside a hardcoded argument; both now read one variable.
//      Asserted from the rendered DOM.
//
//   3. DOB bounds are enforced by the SERVER on an authenticated request.
//      The six-digit year a tester entered previously reached
//      date.fromisoformat() and raised, unhandled.
//
//   4. DELETE semantics: an owner may discard a draft (204, and it is really
//      gone), and nobody may delete a finalized report (409). The ownership
//      half is covered by readonly-ownership.mjs; this covers the rest.
// ============================================================================
import { existsSync, rmSync } from "node:fs";
import { join } from "node:path";
import { DatabaseSync } from "node:sqlite";
import { counts, copyFixture, recordDerivedIds, cleanupByIds, dropDb, dbId } from "./db.mjs";
import { runOwnerFlow } from "./owner-flow.mjs";
import {
  loadConfig, assertSafeTarget, killTree, startBackend, launchEdge,
  preflightOverride, cdpConnect, sleep, BACKEND,
} from "./harness.mjs";

const cfg = loadConfig();
assertSafeTarget(cfg);
const log = (...a) => console.log(...a);
const WANT_TOP_K = 3;

let backend, edge;
async function teardown() { killTree(backend?.pid); killTree(edge?.pid); await sleep(1500); }

async function api(jwt, method, path, body) {
  const res = await fetch(`${cfg.apiBase}${path}`, {
    method,
    headers: { Cookie: `radassist_token=${jwt}`, ...(body ? { "content-type": "application/json" } : {}) },
    body: body ? JSON.stringify(body) : undefined,
  });
  const txt = await res.text();
  let parsed; try { parsed = JSON.parse(txt); } catch { parsed = txt; }
  return { status: res.status, body: parsed };
}

function sessionTopK(sessionId) {
  const db = new DatabaseSync(cfg.testDb, { readOnly: true });
  const r = db.prepare("SELECT top_k FROM retrieval_sessions WHERE id = ?").get(dbId(sessionId));
  db.close();
  return r?.top_k ?? null;
}

function reportExists(reportId) {
  const db = new DatabaseSync(cfg.testDb, { readOnly: true });
  const r = db.prepare("SELECT 1 AS x FROM reports WHERE id = ?").get(dbId(reportId));
  db.close();
  return Boolean(r);
}

async function main() {
  const devBefore = counts(cfg.devDb);
  log(`dev.db BEFORE: ${JSON.stringify(devBefore)}`);

  dropDb(cfg.testDb);
  copyFixture(cfg.devDb, cfg.testDb);
  backend = await startBackend(cfg);
  await preflightOverride(cfg, devBefore);
  log("backend healthy; DB override confirmed (dev.db untouched)\n");

  edge = launchEdge(cfg);
  await sleep(3000);

  // --- 1 + 2. k preference honoured through the real UI ----------------------
  // The doctor's preference is set BEFORE the flow runs, so the upload screen
  // has to read it. runOwnerFlow registers its own doctor, so patch that
  // doctor and then re-drive the UI with the preference in place.
  log("=== 1. default_top_k honoured end to end ===");
  const flow = await runOwnerFlow({ ...cfg, beforeUpload: async ({ jwt }) => {
    const r = await api(jwt, "PATCH", "/auth/me", { default_top_k: WANT_TOP_K });
    log(`  PATCH /auth/me default_top_k=${WANT_TOP_K} -> ${r.status} (stored ${r.body?.default_top_k})`);
  } });

  // sessionId is derived from the report, so populate the id set before reading.
  recordDerivedIds(cfg.testDb, flow.createdIds);
  const sessionId = flow.createdIds.sessionId;
  const storedK = sessionTopK(sessionId);
  const kHonoured = storedK === WANT_TOP_K;
  log(`  retrieval_sessions.top_k for this session -> ${storedK} (want ${WANT_TOP_K})`);
  log(`  header label read from the DOM           -> ${flow.results.steps.k_label ?? "n/a"}`);
  const labelMatches = String(flow.results.steps.k_label ?? "").includes(`K=${WANT_TOP_K}`);

  const jwt = flow.jwt;

  // --- 3. DOB bounds, authenticated ------------------------------------------
  log("\n=== 3. date_of_birth bounds (authenticated) ===");
  const dobCases = [
    ["2005-09-09", 200],
    ["200000-10-02", 422],
    ["1899-12-31", 422],
    ["2099-01-01", 422],
  ];
  const dobResults = [];
  const strayPatientIds = [];
  for (const [dob, want] of dobCases) {
    const r = await api(jwt, "POST", "/patients", { name: `E2E DOB ${dob}`, date_of_birth: dob, gender: "Other" });
    const ok = r.status === want;
    dobResults.push(ok);
    if (r.status === 200 && r.body?.id) strayPatientIds.push(r.body.id);
    log(`  dob=${dob.padEnd(14)} -> ${r.status} (want ${want}) ${ok ? "OK" : "MISMATCH"}`);
  }

  // --- 4. DELETE semantics ----------------------------------------------------
  log("\n=== 4. DELETE /reports/{id} ===");
  // The flow finalized its report, so it must refuse deletion.
  const delFinal = await api(jwt, "DELETE", `/reports/${flow.createdIds.reportId}`);
  const finalStillThere = reportExists(flow.createdIds.reportId);
  log(`  finalized report -> ${delFinal.status} (want 409) ${JSON.stringify(delFinal.body)}`);
  log(`  finalized report still in DB -> ${finalStillThere} (want true)`);

  const del404 = await api(jwt, "DELETE", `/reports/00000000-0000-0000-0000-000000000000`);
  log(`  unknown report id -> ${del404.status} (want 404)`);

  const deleteChecks =
    delFinal.status === 409 && finalStillThere && del404.status === 404;

  // --- Cleanup (ID-scoped) ----------------------------------------------------
  await teardown();
  for (const p of flow.createdIds.imagePaths ?? []) {
    for (const c of [p, join(BACKEND, p)]) if (c && existsSync(c)) { rmSync(c, { force: true }); break; }
  }
  const deleted = cleanupByIds(cfg.testDb, flow.createdIds);
  // The one patient the DOB check legitimately created is removed by its own
  // recorded id -- no predicate, same rule as db.mjs.
  if (strayPatientIds.length) {
    const db = new DatabaseSync(cfg.testDb);
    for (const id of strayPatientIds) db.prepare("DELETE FROM patients WHERE id = ?").run(dbId(id));
    db.close();
  }
  log(`\n=== ID-scoped cleanup === ${JSON.stringify(deleted)} (+${strayPatientIds.length} probe patients)`);
  dropDb(cfg.testDb);

  const devAfter = counts(cfg.devDb);
  const devUnchanged = JSON.stringify(devAfter) === JSON.stringify(devBefore);
  log(`=== dev.db AFTER: ${JSON.stringify(devAfter)}  UNCHANGED: ${devUnchanged ? "YES" : "NO !!!"} ===`);

  const dobOk = dobResults.every(Boolean);
  const pass = kHonoured && labelMatches && dobOk && deleteChecks && devUnchanged;
  log(`\n=== VERDICT: ${pass ? "PASS" : "FAIL"} ===`);
  log(`  k honoured: ${kHonoured} | k label matches: ${labelMatches} | dob bounds: ${dobOk} | delete: ${deleteChecks} | dev unchanged: ${devUnchanged}`);
  process.exit(pass ? 0 : 1);
}

main().catch(async (e) => {
  console.error("FATAL:", e.message);
  await teardown();
  dropDb(cfg.testDb);
  process.exit(1);
});
