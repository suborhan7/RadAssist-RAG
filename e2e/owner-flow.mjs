// e2e/owner-flow.mjs
// ============================================================================
// Drives the OWNER happy-path through the real UI over CDP:
//   register (API) -> upload (real file input) -> retrieve -> questionnaire
//   -> generate -> owner workspace -> edit -> finalize -> downstream views.
//
// It RECORDS every id it creates (doctorId from the register response, reportId
// from the post-generation redirect) and returns them. It performs NO deletion
// -- cleanup is ID-scoped in db.mjs. The DB it writes to is whatever the backend
// under `apiBase` points at; the harness (run.mjs) makes that a disposable copy.
// ============================================================================
import { writeFileSync, existsSync } from "node:fs";

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

export async function runOwnerFlow(cfg) {
  const { apiBase, frontendBase, cdpPort, image: imagePath, patientId, outDir } = cfg;
  if (!existsSync(imagePath)) throw new Error(`image not found: ${imagePath}`);

  const issues = { console: [], exceptions: [], http: [] };
  const results = { steps: {} };
  const createdIds = { doctorId: null, reportId: null };
  const mark = (k, v) => { results.steps[k] = v; console.log(`    → ${k}: ${v}`); };

  // --- 1. Register a fresh doctor via the API; record its id + auth cookie ----
  const email = `e2e-owner-${Date.now()}@example.test`;
  const reg = await fetch(`${apiBase}/auth/register`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ email, password: "e2epass12345", full_name: "E2E Owner (disposable)" }),
  });
  if (!reg.ok) throw new Error(`register failed: ${reg.status} ${await reg.text()}`);
  const regBody = await reg.json();
  createdIds.doctorId = regBody.doctor?.id ?? regBody.id;
  const setCookies = reg.headers.getSetCookie?.() ?? [];
  const jwt = (setCookies.find((c) => c.startsWith("radassist_token=")) || "").split(";")[0].split("=")[1];
  if (!createdIds.doctorId || !jwt) throw new Error("register did not yield doctorId + token");
  mark("register", `doctorId=${createdIds.doctorId}`);

  // --- CDP plumbing -----------------------------------------------------------
  let nextId = 1;
  const pending = new Map();
  const wsUrl = await (async () => {
    for (let i = 0; i < 30; i++) {
      try {
        const t = (await (await fetch(`http://localhost:${cdpPort}/json`)).json()).find(
          (x) => x.type === "page" && x.webSocketDebuggerUrl,
        );
        if (t) return t.webSocketDebuggerUrl;
      } catch {}
      await sleep(500);
    }
    throw new Error("no CDP page target");
  })();
  const ws = new WebSocket(wsUrl);
  await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
  const send = (method, params = {}) => {
    const id = nextId++;
    ws.send(JSON.stringify({ id, method, params }));
    return new Promise((resolve, reject) => {
      pending.set(id, { resolve, reject });
      setTimeout(() => { if (pending.has(id)) { pending.delete(id); reject(new Error("timeout " + method)); } }, 120000);
    });
  };
  ws.onmessage = (ev) => {
    const m = JSON.parse(ev.data);
    if (m.id && pending.has(m.id)) {
      const p = pending.get(m.id); pending.delete(m.id);
      return m.error ? p.reject(new Error(m.error.message)) : p.resolve(m.result);
    }
    if (m.method === "Runtime.consoleAPICalled" && ["error", "warning", "assert"].includes(m.params.type))
      issues.console.push({ type: m.params.type, txt: (m.params.args || []).map((a) => a.value ?? a.description ?? a.type).join(" ").slice(0, 300) });
    if (m.method === "Runtime.exceptionThrown")
      issues.exceptions.push((m.params.exceptionDetails.exception?.description || m.params.exceptionDetails.text || "exception").slice(0, 300));
    if (m.method === "Network.responseReceived" && m.params.response.status >= 400)
      issues.http.push({ status: m.params.response.status, url: m.params.response.url.replace(/^https?:\/\/localhost:\d+/, "") });
  };
  const evalJs = async (expression, awaitPromise = false) => {
    const r = await send("Runtime.evaluate", { expression, awaitPromise, returnByValue: true });
    if (r.exceptionDetails) throw new Error("eval: " + (r.exceptionDetails.exception?.description || r.exceptionDetails.text));
    return r.result.value;
  };
  const shot = async (name) => {
    if (!outDir) return;
    const { data } = await send("Page.captureScreenshot", { format: "png", clip: { x: 0, y: 0, width: 1440, height: 900, scale: 1 } });
    writeFileSync(`${outDir}/e2e-${name}.png`, Buffer.from(data, "base64"));
  };
  const waitFor = async (expr, { timeout = 30000, interval = 800 } = {}) => {
    const t0 = Date.now();
    while (Date.now() - t0 < timeout) { try { if (await evalJs(expr)) return true; } catch {} await sleep(interval); }
    return false;
  };
  const click = (labels) => evalJs(`(()=>{const w=${JSON.stringify([].concat(labels))};const els=[...document.querySelectorAll('button,a')];for(const t of w){const e=els.find(x=>x.textContent.trim()===t)||els.find(x=>x.textContent.trim().startsWith(t));if(e){e.click();return t;}}return null;})()`);
  const navigate = async (url) => { await send("Page.navigate", { url }); await waitFor("document.readyState==='complete'", { timeout: 15000 }); };

  await send("Page.enable");
  await send("Runtime.enable");
  await send("Network.enable");
  await send("DOM.enable");
  await send("Emulation.setDeviceMetricsOverride", { width: 1440, height: 900, deviceScaleFactor: 1, mobile: false });
  await send("Network.setCookie", { name: "radassist_token", value: jwt, domain: "localhost", path: "/", httpOnly: true, secure: false, sameSite: "Lax" });

  // Optional hook for callers that need to change something about the doctor
  // BEFORE the upload screen renders (qa-fixes.mjs sets default_top_k here, so
  // the screen has to read the preference rather than a literal).
  if (typeof cfg.beforeUpload === "function") await cfg.beforeUpload({ jwt, doctorId: createdIds.doctorId });

  // --- 2. Upload page + real file input --------------------------------------
  await navigate(`${frontendBase}/patients/${patientId}/upload`);
  await sleep(1200); await shot("01-upload");
  // The header's k readout, captured from the DOM. It used to be the literal
  // string "K=5" sitting beside a literal `topK: 5`; both now read one value,
  // and this is how a caller proves the label agrees with the request.
  mark("k_label", await evalJs(`(document.querySelector('header')?.innerText || '').replace(/\\s+/g,' ').trim()`));
  const { root } = await send("DOM.getDocument", { depth: -1 });
  const { nodeId } = await send("DOM.querySelector", { nodeId: root.nodeId, selector: "input[type=file]" });
  await send("DOM.setFileInputFiles", { nodeId, files: [imagePath] });
  await sleep(1500); await shot("02-file-selected");

  // --- 2b. Declare the projection (requirement A14) --------------------------
  // Added when input_admission_projection_gate_architecture_v1.1 landed.
  // A14 makes the declared projection mandatory and A15 forbids a default,
  // so "Start examination" now stays disabled until a view is chosen. A file
  // alone is no longer enough, and without this step the harness clicked a
  // disabled button and the flow stalled with no error.
  //
  // Scoped to `button[aria-pressed]`, the projection group's own hook, rather
  // than matching the visible text "PA" across the whole document -- a
  // two-letter label is too easy to collide with.
  const projection = await evalJs(`(()=>{const b=[...document.querySelectorAll('button[aria-pressed]')].find(x=>x.textContent.trim()==='PA');if(!b)return null;b.click();return b.textContent.trim();})()`);
  mark("projection_declared", projection === "PA" ? "PASS" : "FAIL");
  await sleep(400); await shot("02b-projection-declared");

  // Once a file is chosen AND a projection is declared, the upload page swaps
  // the <input> for the film preview, so assert the file was *accepted*
  // (Start enabled), not that the input remains.
  mark("file_accepted", (await evalJs(`(()=>{const b=[...document.querySelectorAll('button')].find(x=>x.textContent.includes('Start examination'));return b?!b.disabled:false;})()`)) ? "PASS" : "WARN");

  // --- 3. Run pipeline; wait for the questionnaire Skip button ----------------
  await click("Start examination");
  await sleep(2000); await shot("03-retrieval");
  const qReady = await waitFor(`[...document.querySelectorAll('button')].some(b=>b.textContent.trim()==='Skip and draft anyway')`, { timeout: 60000, interval: 1000 });
  mark("retrieval+questionnaire", qReady ? "PASS" : "FAIL");
  await click("Skip and draft anyway");

  // --- 4. Generation -> redirect to the owned report -------------------------
  const gotReport = await waitFor(`/\\/reports\\//.test(location.href)`, { timeout: 150000, interval: 1500 });
  await sleep(2000);
  const url = await evalJs("location.href");
  createdIds.reportId = gotReport ? url.match(/reports\/([^/?]+)/)?.[1] ?? null : null;
  mark("generation", gotReport ? `PASS reportId=${createdIds.reportId}` : "FAIL");
  if (!gotReport) { ws.close(); return { createdIds, results, issues }; }
  await shot("04-owner-workspace");

  // --- 5. Owner workspace: controls present ----------------------------------
  mark("owner_controls", await evalJs(`JSON.stringify({finalizeBtn:[...document.querySelectorAll('button')].some(b=>b.textContent.trim()==='Finalize'),readOnly:/belongs to/.test(document.body.innerText),status:(document.body.innerText.match(/AI Draft|Doctor Edited|Final/)||[''])[0]})`));

  // --- 6. Edit the Findings section ------------------------------------------
  await evalJs(`(()=>{const h=[...document.querySelectorAll('h3')].find(x=>/FINDINGS/i.test(x.textContent));const s=h&&(h.closest('.group')||h.closest('div'));const b=s&&[...s.querySelectorAll('button')].find(x=>x.textContent.trim()==='Edit');b&&b.click();})()`);
  await waitFor(`!!document.querySelector('textarea')`, { timeout: 5000 });
  await shot("05-edit-mode");
  await evalJs(`(()=>{const ta=document.querySelector('textarea');if(!ta)return;const set=Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype,'value').set;set.call(ta,ta.value+' E2E-edit.');ta.dispatchEvent(new Event('input',{bubbles:true}));ta.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true}));})()`);
  await sleep(2000);
  mark("edit", (await evalJs(`/E2E-edit\\./.test(document.body.innerText)&&/Doctor Edited|Edited/.test(document.body.innerText)`)) ? "PASS" : "WARN");

  // --- 7. Finalize ------------------------------------------------------------
  await click("Finalize");
  await waitFor(`/Preview before finalizing|Confirm Finalize/.test(document.body.innerText)`, { timeout: 6000 });
  await shot("06-finalize-preview");
  await click("Confirm Finalize");
  const finalized = await waitFor(`/Finalized by/.test(document.body.innerText)||[...document.querySelectorAll('*')].some(e=>e.textContent.trim()==='Final')`, { timeout: 60000, interval: 1500 });
  await sleep(1500); await shot("07-finalized");
  mark("finalize", finalized ? "PASS" : "FAIL");

  // --- 8. Downstream: compare (creates a comparison row we will clean up) -----
  await navigate(`${frontendBase}/reports/${createdIds.reportId}/compare`);
  await waitFor(`/Doctor review required|Narrative|Generating comparison/.test(document.body.innerText)`, { timeout: 20000 });
  await sleep(16000); await shot("08-compare");
  mark("compare", (await evalJs(`/RESOLVED|PERSISTENT|Narrative/.test(document.body.innerText)`)) ? "PASS" : "check");

  ws.close();
  // jwt is returned so a caller can keep acting as this doctor after the flow
  // (qa-fixes.mjs checks DOB bounds and DELETE with it) without registering a
  // second account whose rows would then need their own cleanup.
  return { createdIds, results, issues, jwt };
}
