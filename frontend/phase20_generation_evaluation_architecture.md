## Phase 20 — Generation-Quality Evaluation: Architecture (FROZEN)

**Status: frozen, pending implementation.** Amended per external review
(fail-fast test-purity gate covering both index metadata and source
embedding cache, determinism/generation-parameter recording, adaptive
sample size, bootstrap settings anchored to Phase 0's real configuration
rather than invented numbers, failure logging, saved per-case outputs,
`evaluation_config.json`) before freeze. Same discipline as every prior
phase from here: step-by-step, real execution output at each gate,
confirmed before proceeding.

### Why this phase, and what it doesn't need to build

Retrieval quality is **already evaluated** — Phase 0's encoder-validation
gate (BiomedCLIP vs. random vs. generic CLIP, class-stratified bootstrap
CIs on Recall@5/nDCG@10, a pre-registered gate decision table) is real,
complete, and already written up. This phase does not touch retrieval.

What's missing is **generation quality**: does the LLM-drafted report,
grounded in retrieved evidence, actually resemble what a real
radiologist wrote for the same image? That comparison has never been
run. This phase scopes it.

### Decisions requiring investigation before anything runs (hard gate)

1. **Test-set purity is a fail-fast gate, not a check-and-continue.**
   Phase 0's leakage-safe split (`splits.csv`) reserved a `test` split
   specifically to be "touched exactly once." Verify **both**: (a) the
   ChromaDB collection's own metadata (which studies it was built from),
   and (b) the source embedding cache used to build it — metadata alone
   could be stale if the collection was rebuilt without updating its own
   records. Prove `index_contents ⊆ (train ∪ validation)`, strictly
   excluding `test`. **If this gate fails, Phase 20 pauses immediately
   and the retrieval index must be rebuilt before any evaluation runs**
   — not a warning to continue past. If ChromaDB's index was ever built
   from the full dataset rather than strictly train/val, evaluation
   images could retrieve themselves or near-duplicates, silently
   inflating every metric that follows. Locate the actual source
   embedding cache's real path before checking it — confirm where it
   lives, don't assume a path from the ML pipeline's documentation
   alone.
2. **Ground-truth field mapping must be confirmed, not assumed
   symmetric.** The live system generates 7 structured fields
   (`examination`, `clinical_history`, `technique`, `findings`,
   `impression`, `recommendation`, `disclaimer`), but the IU dataset's
   real radiologist reports were only ever columns like `findings`/
   `impression`/`indication`/`comparison` (per the ML pipeline's own
   `master_metadata.csv` schema) — there is no ground-truth `technique`
   or `disclaimer` to compare against. **Evaluate only `findings` and
   `impression`** — the two fields that both have real ground truth and
   are the two fields Phase 17's own finalize-validation already treats
   as clinically essential (non-empty required). Confirm this mapping
   against the real `master_metadata.csv` columns before writing any
   comparison code, not assumed from column names alone.

### Decisions frozen (pending approval)

3. **Evaluation calls the real backend HTTP API, not backend internals
   directly.** This respects the project's own established, deliberate
   boundary ("`ml/` and `backend/` never import each other except
   through the `shared/` exception") rather than quietly violating it
   for evaluation-script convenience. A script under `ml/evaluation/`
   (matching Phase 0's existing location and naming convention —
   `run_generation_eval.py`, alongside `run_encoder_eval.py`) drives the
   real generation pipeline through its real API, the same path a
   doctor's browser uses.
4. **Evaluation runs with no questionnaire answers and no clinical
   notes** — matching the honest default (the real frontend currently
   sends `clinical_notes=""` on every real call, and questionnaire is
   frequently skipped, per earlier findings). This is the single
   cleanest, most reproducible condition to report as the headline
   number. A with-questionnaire ablation is real, valuable, and
   explicitly deferred — see Explicitly Not In Scope.
5. **Generation parameters are recorded alongside every evaluation run
   and fixed for the entire experiment** — model name, Ollama version,
   prompt version/hash, `temperature`, `top_p`, `repeat_penalty`, seed
   (if the backend's Ollama integration supports one), max tokens.
   Without this, a BLEU score from this run is unexplainable six months
   later if any of these silently drifted. Confirm what's actually
   configurable/loggable in the real `LLMOrchestrator`/Ollama client
   before assuming all of these are available — report what's real
   before the run starts, not after.
6. **Sample size is adaptive, not hard-frozen at 100.** Default target:
   100 held-out cases. If the verified-untouched test split (Decision 1)
   contains fewer than 100 studies, evaluate all of them. If it contains
   more and compute budget allows, evaluating the full untouched split
   is preferable to an arbitrary cap. One footnote worth stating in the
   thesis regardless of which N is used: bootstrap CIs already account
   for finite-sample uncertainty, and published radiology report-
   generation evaluations commonly use samples in a similar range — so
   there's no methodological obligation to maximize N past the point of
   diminishing statistical return just because the GPU has headroom;
   100–200 is a defensible stopping point on its own if the full split
   is much larger.
7. **Metrics, tiered by cost, not all promised at once:**
   - **Tier 1 (always run): BLEU, ROUGE-L, METEOR.** Cheap, standard,
     no model downloads, directly comparable to prior radiology report-
     generation literature.
   - **Tier 2 (run if a domain-appropriate model is confirmed available):
     BERTScore using a biomedical BERT variant** (PubMedBERT/BioBERT,
     not generic BERT — semantic similarity in clinical text needs a
     clinically-trained embedding space to mean anything). Confirm the
     model can actually be downloaded/run in this environment before
     committing to it in the results chapter.
   - **Tier 3 (stretch, not promised): CheXbert F1** — extracts clinical
     entities/labels from both generated and reference text and compares
     them, giving a metric that's actually about clinical content rather
     than word overlap. Named explicitly as a stretch goal because it
     requires downloading and running a real, sizeable additional model
     — worth attempting, not worth blocking the rest of the chapter on.
8. **Report point estimates with bootstrap confidence intervals, using
   the exact same configuration `analyze_results.py` already used for
   Phase 0** (resample count, confidence level, case-level vs. pooled
   resampling, seed) — do not invent a second, different bootstrap
   configuration for this chapter. If `analyze_results.py`'s actual
   settings turn out to differ from a "standard" choice like 10,000
   resamples / 95% CI, match what Phase 0 really used, and only deviate
   with an explicit stated reason. Two evaluation chapters in the same
   thesis using silently different statistical methodology would be a
   real, avoidable inconsistency.
9. **Generation failures are recorded, not silently skipped.** If a
   case fails (Ollama crash, timeout, malformed JSON, backend error),
   the per-case CSV records `status=generation_failed` and a `reason`,
   not an omitted row. The summary reports both the completed and
   failed counts explicitly (e.g. "97 completed, 3 failed") — a report
   that silently evaluates on however many cases happened to succeed,
   with no record of the denominator, overstates its own completeness.
10. **Save per-case generated output, not just scores.** Alongside the
    results CSV, persist each case's actual generated `findings`/
    `impression` text (plain files or a JSON blob per case). "Why did
    BLEU drop on case 41" is a question this evaluation will provoke,
    and answering it without the generated text means rerunning the
    whole experiment. Keeping the text is nearly free and makes the
    evaluation actually reproducible/inspectable after the fact.
11. **Output artifacts live in `ml/evaluation/`**, matching Phase 0's
    existing convention (`gate_decision_table.csv`-style precedent):
    a per-case results CSV, a summary table, per-case generated text
    (Decision 10), and one `evaluation_config.json` tying the whole run
    together — model version, prompt version, decoding settings
    (Decision 5), metric versions/library versions, bootstrap seed and
    configuration (Decision 8), sample size and its source (Decision 6),
    evaluation date, and the git commit hash of both `ml/` and `backend/`
    at run time. This one file is what makes the run reproducible
    without having to reconstruct settings from memory or scattered
    notes.

### Step breakdown

1. **Hard gate — confirm test-set purity, both index metadata and
   source embedding cache** (Decision 1). If it fails, stop and report;
   do not proceed to any other step until the index is rebuilt and
   re-verified.
2. **Confirm ground-truth field mapping** (Decision 2) against the real
   `master_metadata.csv` schema.
3. Confirm Tier 2's biomedical BERT model is actually obtainable in this
   environment (Decision 7) — report yes/no before committing to it in
   the plan.
4. Confirm what generation parameters are actually recorded/configurable
   in the real `LLMOrchestrator`/Ollama integration (Decision 5) —
   report what's real, don't assume every listed parameter is exposed.
5. Confirm `analyze_results.py`'s real bootstrap configuration (Decision
   8) before writing any new bootstrap code — reuse those exact settings
   or state explicitly why this chapter deviates.
6. Write `ml/evaluation/run_generation_eval.py`: for each test image
   (Decision 6's adaptive N), call the real backend API end-to-end
   (upload → mask → retrieve → generate, no questionnaire), capture
   `findings`/`impression` and the full generated text (Decision 10),
   compare against ground truth, compute Tier 1 metrics per-case. Record
   `status`/`reason` for any failed case rather than skipping it
   (Decision 9).
7. Bootstrap CI computation using the confirmed Phase 0 configuration
   (Decision 8).
8. Tier 2 (and Tier 3, if attempted) added as a second pass once Tier 1
   is verified working end-to-end — don't build all three tiers at once
   and discover a bug in the cheap tier only after the expensive one
   already ran.
9. Write `evaluation_config.json` (Decision 11) once all settings are
   confirmed real, not as an afterthought — this should be produced by
   the same run it describes, not reconstructed later from memory.
10. Real output: the per-case CSV, per-case generated text, summary
    table, and config file, reviewed for sanity (spot-check a handful of
    generated-vs-reference pairs by eye, not just trust the aggregate
    numbers) before calling this phase complete.

### Risks

- **If Step 1 finds the test split isn't actually clean**, this phase's
  scope changes materially (may need a fresh, verified-untouched holdout
  cut from data never indexed) — report this before proceeding, don't
  quietly evaluate on a compromised set.
- **100 real generations is real GPU time and real Ollama load** — worth
  running when nothing else is competing for the GPU, and worth noting
  in the methodology that timing/latency figures from this run
  shouldn't be treated as representative of single-user interactive
  latency (per the earlier flaky-test finding about load-conditional
  behavior).
- **BLEU/ROUGE reward surface word overlap, not clinical correctness** —
  a report that rephrases correctly could score low; this is a known,
  citable limitation of these metrics in the radiology-NLG literature,
  not a bug in this evaluation. State it plainly in the thesis rather
  than letting a low BLEU score look like a system failure.

### Explicitly not in scope for this phase

- Questionnaire-present vs. questionnaire-absent ablation (real,
  valuable, a natural Phase 21 candidate — the design was already
  gesturing at this kind of ablation early on).
- CheXbert/RadGraph as guaranteed deliverables (Tier 3, stretch only).
- Human/radiologist evaluation of generated reports (separate track,
  needs its own recruitment/protocol, not a code task).
- Evaluating the Report Edit Percentage (REP) data as a second,
  independent evaluation signal — genuinely worth doing (Phase 18
  already collects this on every real report), but is a different data
  source (real doctor behavior, not held-out ground truth) and deserves
  its own short scoping pass, not folded into this one.

---

**Once frozen, implementation follows this project's standing
discipline: step-by-step, real execution output at each gate, confirmed
before proceeding, `development_log.md` updated with the same
four-part structure as every prior phase.**
