# Phase 21 — Evidence Ablation & Latency Characterisation: Architecture

**Status: FROZEN (draft 2).** Approved and frozen with §3.2–§3.7 exactly as revised. Implementation proceeds strictly through the gated step sequence in §8, beginning at Step 0. No change to this document without an explicit unfreeze.

**Prerequisite phases:** Phase 0 (encoder selection), Phase 4 (RetrievalService, LabelVotingService), Phase 5 (ContextBuilder), Phase 6 (PromptBuilder), Phase 7 (LLMOrchestrator), Phase 8 (ResponseValidator, ReportFormatter), Phase 20 (Generation-Quality Evaluation).

---

## 1. Objective

Phase 20 established **how well** this system's generated reports match ground truth. It did not establish **why** — specifically, whether the retrieval-augmented architecture contributes anything beyond what a simpler design would achieve. That gap is the central claim of the thesis title and is currently unmeasured.

Phase 21 measures it, and additionally produces the per-stage latency characterisation that the resource-constrained-deployment argument requires.

This is an **evaluation phase, not a feature-build phase**, with two exceptions that are prerequisites for a valid measurement (§3 and §4).

### 1.1 Research questions

| ID | Question | Arms compared |
|---|---|---|
| **RQ1** | Does retrieved report *text* improve generation quality beyond retrieved *labels* alone? | C vs B |
| **RQ2** | Does retrieval-derived evidence of any kind improve generation quality over none? | C vs A |
| **RQ3** | What is the per-stage latency profile of the deployed pipeline on the target hardware? | C only |

**RQ1 is the primary question.** Arm B is functionally the modern equivalent of the classify-then-template approach the project abandoned after Phase 0's encoder bake-off; RQ1 is therefore the direct empirical justification for the retrieval-augmented design over a classification-based one.

---

## 2. Arm definitions

All three arms run **the identical production code path**. They differ only in the content of the `ClinicalContext` assembled by `ContextBuilder`.

| Arm | Retrieved case text | Voted labels | Clinical notes / questionnaire / demographics |
|---|---|---|---|
| **A — `empty`** | ✗ | ✗ | ✓ |
| **B — `labels_only`** | ✗ | ✓ | ✓ |
| **C — `full`** | ✓ | ✓ | ✓ |

### 2.1 Naming discipline (non-negotiable)

Arm B **must not** be described as "no retrieval" in the dev log, the thesis, or the defense. Retrieval still executes in Arm B; its output is reduced to voted labels. The accurate description is **"retrieval-as-classifier"**. Arm A is the only arm with no retrieval-derived evidence, and even there retrieval still runs to create the session — only its output is discarded before context assembly.

Any wording that implies Arm B bypasses BiomedCLIP or ChromaDB is a misstatement of the experiment and will not survive examiner questioning.

### 2.2 Where the arm takes effect

**Decision: `ContextBuilder` (Phase 5), driven by a configuration value, not a request parameter.**

Rejected alternatives and why:

| Alternative | Rejected because |
|---|---|
| Request parameter on `POST /generate-report` | Adds an evaluation-only knob to a production API contract; a caller could invoke a degraded mode in production |
| Dedicated evaluation endpoint | Violates "measure what you ship" — the ablation would no longer exercise the real path |
| Filtering inside `PromptBuilder` | Two components would then own evidence composition; `ClinicalContext` would no longer reflect what the LLM actually received |

**Mechanism:** a new `EVIDENCE_MODE` setting in `backend/app/core/config.py`, typed as an enum (`full` | `labels_only` | `empty`), defaulting to `full`. `ContextBuilder` reads it via the existing injected `Settings` dependency. Production and every non-evaluation environment run `full`; the default is never changed in any committed configuration file.

**Consequence, stated explicitly:** each arm requires a backend restart with a different environment value. Arms therefore run sequentially, not interleaved. This is accepted, with two mitigations recorded in §7.

**Confirm during Step 0:** that `ContextBuilder` already receives `Settings` by injection. If it does not, the injection must be added as a separate, individually-gated step before any ablation logic, because it modifies a frozen Phase 5 file.

---

## 3. Prerequisite fix — disclaimer removal from LLM output schema

### 3.1 Justification

Three independent reasons, in order of weight:

1. **Clinical safety.** A legal/safety disclaimer must be deterministic and controlled. A model-generated disclaimer can be silently reworded, softened, or omitted. This is a defect in the current design regardless of the ablation.
2. **Failure-mode elimination by construction.** All 17 of Phase 20's generation failures share one signature — a JSON parse error at the `disclaimer` field. Removing the field from the model's output eliminates the failure mode rather than escaping around it.
3. **Measurement validity.** Arm-wise differences in generation failure rate would confound the comparison. A failure mode concentrated in one schema position is the largest known source of such a difference.

### 3.2 Correction to draft 1 — the disclaimer is NOT boilerplate

Draft 1 proposed replacing the disclaimer with a static configured constant. **The §11.3 verification found that assumption to be wrong**, and the corrected design below supersedes it.

Evidence from the dev log's own Phase 7 integration output:

```
--- disclaimer ---
Clinical uncertainty due to low agreement score (0.60)
```

The field is **case-specific**: it cites the real `VotedLabel.agreement` value produced by `LabelVotingService` for that run. The Phase 7 entry explicitly records this as evidence that Phase 6's confidence-framing and grounding instructions are being followed, "rather than generic boilerplate."

Further, the field has a **downstream consumer**. Phase 10's Explainability Assistant reads it: the recorded integration output shows the model citing the 0.60 agreement score by name when answering a clinician's question.

A static constant would therefore destroy two documented, working, thesis-relevant behaviours. That proposal is withdrawn.

### 3.3 Corrected design — server-rendered parameterised template

The disclaimer is a **confidence statement derived from a deterministic quantity the backend already computes**. `VotedLabel.agreement` is calculated by `LabelVotingService` before the LLM is ever called. The model's only contribution is paraphrasing a number it was handed into prose — which adds no information and introduces the JSON-escaping hazard.

**Design:** the backend renders the disclaimer from a configured template, parameterised on the real agreement value and the report language.

```
REPORT_DISCLAIMER_TEMPLATE_EN = "Clinical uncertainty due to {band} agreement score ({agreement:.2f})."
REPORT_DISCLAIMER_TEMPLATE_BN = "..."
REPORT_DISCLAIMER_NO_EVIDENCE_EN = "..."   # fallback, see §3.5
REPORT_DISCLAIMER_NO_EVIDENCE_BN = "..."
```

The `{band}` qualifier (`low` / `moderate` / `high`) comes from the existing rule-based confidence banding, not from the model.

This is **strictly better than the current behaviour**, not merely equivalent:

| Property | LLM-generated (current) | Server-rendered (proposed) |
|---|---|---|
| Agreement score is case-specific | ✓ | ✓ |
| Explainability Assistant can cite it | ✓ | ✓ |
| Score is guaranteed to match the real computed value | **✗ — never verified** | ✓ |
| Immune to JSON escaping failure | ✗ | ✓ |
| Wording controlled for clinical safety | ✗ | ✓ |

The third row is the one worth stating at defense: nothing in this project has ever verified that the model transcribes the agreement score correctly. It could paraphrase 0.60 as 0.6, as "approximately 0.6", or wrongly. Server-rendering makes the number correct by construction rather than by trust.

### 3.4 Scope — deliberately narrow

`disclaimer` is **retained** on the `ReportContent` entity, in the `reports` table, in the API response, in the rendered report, and in the frontend. Only the LLM's obligation to emit it is removed.

This avoids a database migration, a frontend change, and an i18n key change. Blast radius:

| File | Change |
|---|---|
| `backend/app/core/config.py` | Add the four templates above |
| `backend/app/services/prompt_builder.py` | `REPORT_CONTENT_FIELDS` 7 → 6; prompt text updated to stop requesting the field |
| `backend/app/services/structural_validator.py` | Expected-key set 7 → 6 |
| Assembly point (`LLMOrchestrator` or `ReportGenerationService` — confirm in Step 0) | Render the template from the real `VotedLabel.agreement` and language, inject into `ReportContent` after parsing |
| Affected unit tests | Updated to the 6-field contract; new tests for template rendering and the no-evidence fallback |

`prompt_builder.py`, `structural_validator.py`, and the orchestrator are **frozen files**. Each edit is individually gated.

### 3.5 Ablation interaction — the no-evidence fallback

Arm A (`empty`) has no voted labels, therefore no agreement score, therefore no value to render the primary template from. A separate no-evidence template variant is required.

This is not an edge case invented for the ablation: it is the correct behaviour for any future case where retrieval returns nothing, and it should exist regardless. The ablation merely surfaced it.

### 3.6 Bilingual requirement

The Bengali templates are subject to the same **provisional / not clinician-reviewed** marking as all other Bengali content in this project, recorded in the dev log entry and the thesis limitations section.

### 3.7 Acceptance gate

Three conditions, all required before Phase 21 proceeds:

1. A 30-case smoke run yields **zero** JSON parse failures. Any residual failure at a different field position invalidates the failure-rate parity check in §6.4 and must be diagnosed first.
2. The rendered disclaimer's agreement value is verified against the real `VotedLabel.agreement` for the same case, on at least 5 cases, by direct comparison — not by reading the string.
3. **Explainability regression:** the Phase 10 integration test is re-run and the assistant is confirmed still able to cite the agreement score from the rendered disclaimer. If template wording breaks that behaviour, the wording is adjusted until it does not.

Condition 3 is the one most likely to be skipped and the one whose absence would be noticed at defense.

---

## 4. Prerequisite fix — generation parameters pinned

Phase 20 Step 4 established that only `model` and `temperature` have ever been configured by this backend; `top_p`, `repeat_penalty`, `seed`, and `num_predict` have never been set anywhere in the codebase.

A paired experiment cannot rest on unpinned sampling parameters. But Phase 21 needing controlled generation is **not** a sufficient reason to permanently change what ships.

### 4.1 Capability added, default preserved

The four parameters are added to `Settings` and passed through `OllamaClient` **only when set**, each defaulting to unset. With no environment override, the request body sent to Ollama is byte-identical to today's — production behaviour is unchanged, not merely "expected to be similar."

Phase 21's evaluation runs launch the backend with explicit overrides, using the same environment-variable mechanism as `EVIDENCE_MODE` (§2.2). One mechanism, two uses, no evaluation-only code path.

**Verification:** the unset-default case is covered by a unit test asserting that the outbound options payload contains no key for any unset parameter. "Defaults to unset" is a claim that has to be tested, not asserted.

### 4.2 Consequence, stated rather than buried

Phase 21 therefore measures a configuration that is not identical to the shipped default. This is a real limitation and is recorded as such in `evaluation_config.json`, the dev log entry, and the thesis:

> Ablation results were obtained under pinned sampling parameters to permit a controlled paired comparison. The deployed default leaves these parameters at the inference server's own defaults. The comparison between arms is therefore valid; the absolute values should not be read as production output characteristics.

Whether to adopt pinned parameters in production is a **separate decision, deliberately not bundled into this phase.** It has an independent argument in its favour — the absence of a pinned seed is part of why "deterministic at temperature 0" was never fully guaranteed in the earlier flaky-test investigation — and should be taken on its own merits, after the defense, not smuggled in through an evaluation phase.

### 4.3 Determinism verification gate

Pinning parameters is not the same as achieving determinism. GPU-batched inference non-determinism was previously observed and documented in this project.

**Before any ablation run:** 5 cases × 3 repetitions under `full`, identical inputs. Record whether outputs are byte-identical.

- **Identical:** the paired design proceeds as specified.
- **Not identical:** within-arm variance is real and must be quantified before between-arm differences are interpreted. Add a within-arm repetition subset (5 cases × 5 repetitions per arm) and report within-arm variance alongside between-arm difference. **Do not proceed as if determinism were achieved.**

This gate exists because a between-arm difference smaller than within-arm noise is not a result.

**Scope limit:** determinism observed under the pinned evaluation configuration says nothing about determinism under the unpinned production default. No claim about production determinism may be drawn from this gate.

---

## 5. Relationship to Phase 20

**Phase 20 stands unchanged.** Its results, findings, and negative results are not re-run, not superseded, and not merged with Phase 21's.

Phase 21 runs all three arms fresh under one code version (post-§3, post-§4), so all three are internally comparable. Phase 21's absolute values will differ slightly from Phase 20's because the code differs; **only Phase 21's between-arm differences are claimed**, which is the quantity the research questions ask about.

**Thesis requirement:** Phase 20 and Phase 21 numbers appear in separate tables, never the same one, with a stated note that the code version differs and why.

---

## 6. Measurement design

### 6.1 Case pool and pairing

- Pool: the 477 evaluation-eligible test-split studies established in Phase 20 Step 2 (frontal image + real `findings_clean` + real `impression_clean`, re-derived at runtime).
- **Paired design:** all arms evaluate the identical case list in the identical order, drawn with the same recorded seed. Paired differences have materially lower variance than independent samples, which is what makes a smaller N viable.
- Test-set purity: Phase 20 Step 1's fail-fast gate is re-run, not assumed. The index may have changed since.

### 6.2 Metrics

| Tier | Metric | Included | Rationale |
|---|---|---|---|
| 1 | ROUGE-L | ✓ | Converged to tight CIs in Phase 20 |
| 1 | METEOR | ✓ | As above |
| 1 | BLEU | ✗ | Phase 20 documented an unresolvable short-text fit limitation |
| 2 | BERTScore | ✗ | Phase 20 showed it does not clear a random-baseline validity bar on this dataset |
| 3 | CheXbert macro-F1 | ✓ | Cleared the validity bar for both fields in Phase 20 |

Fields scored: `findings` and `impression`, separately, per Phase 20's convention.

Excluding BLEU and BERTScore is not result-shopping — both exclusions rest on documented, pre-existing negative findings about the *metrics*, established before this phase's arms existed and without knowledge of this phase's outcome.

### 6.3 Pre-registered primary endpoint

Set before any Phase 21 run, per the Phase 0 pre-registered-gate precedent:

> **Primary:** CheXbert macro-F1 on `impression`, Arm C minus Arm B, paired bootstrap 95% CI excludes zero in the positive direction.

All other contrasts (C−A, and every ROUGE-L/METEOR contrast on both fields) are **secondary and exploratory**. With two planned contrasts × three metrics × two fields, twelve intervals are computed; without a designated primary endpoint, at least one crossing zero by chance is likely. Secondary results are reported as a family and described as exploratory, not as independent confirmations.

**If the primary endpoint does not clear:** it is reported as a negative result, in full, consistent with this project's treatment of the Tier 2 BERTScore outcome. No alternative metric, field, or contrast is promoted to primary after the fact.

### 6.4 Failure-rate parity check

Generation failure count and rate are recorded per arm. If rates differ by more than 2 percentage points between any two arms, the cause is investigated and reported before between-arm quality differences are interpreted — differential attrition is a selection effect, not noise.

Note that Arm A is the most likely to fail structurally, having the least context to work from. This is expected and is itself a reportable finding.

### 6.5 Sample size determination

Phase 20 Step 7's own method, reused.

**No final N is pre-committed.** The only fixed quantity is the pilot size; every subsequent extension is decided from measured variance, and the process terminates at whichever comes first — the precision target or pool exhaustion. Any figure appearing in discussion as a likely landing point (150, 200, 300) is an illustration, not a plan, and must not appear in the dev log or thesis as a target.

1. Pilot at **n = 100**, all three arms (≈300 generations).
2. Compute the paired-difference CI width as a percentage of its mean for the primary endpoint.
3. Target ≈20% of mean, matching Phase 20's precision target.
4. Verify the 1/√n width-scaling assumption empirically against a smaller subsample before extrapolating — as in Phase 20, do not assume it.
5. Extend via the harness's existing `--append` mode (same seed, appended not restarted) until the target is met or the 477-case pool is exhausted.
6. If the pool is exhausted without meeting the target, report the achieved precision honestly, as Phase 20 did for `impression_bleu`.

### 6.6 Statistics

Phase 0 and Phase 20's identical configuration: 2,000 resamples, seed 42, 95% CI, percentile method, plain case-level resampling. Applied to the paired per-case difference, not to each arm's mean independently.

---

## 7. Latency characterisation (RQ3)

### 7.1 Instrumentation

An **additive** `timings` block on the relevant API responses, following the Phase 4 Step 11 precedent for additive contract extension. Additive means no existing field changes type or disappears; existing clients are unaffected.

Stages to instrument — **the exact list is confirmed in Step 0 against the real request path**, not assumed from the architecture diagram. Candidates: image validation, PHI masking (confirm whether this executes in the live request path or only in `ml/` preprocessing), BiomedCLIP embedding, ChromaDB query, label voting, context build, prompt build, LLM call, response validation, formatting, persistence. Plus `total_ms`.

This instrumentation does double duty: it is also the backing data for the "Response Time Tracking" feature in the product feature list, so it is not throwaway evaluation scaffolding.

### 7.2 Protocol

- Arm C only. Latency of a degraded arm is not a claim anyone needs.
- Discard the first 3 generations after backend start (cold model load). Phase 4's measured 8.397s first `/retrieve` versus ~0.1s subsequent is exactly this artefact and must not enter the table.
- 30–50 warm runs.
- Report **P50 and P95 per stage**, not means — latency distributions are right-skewed and a mean understates the tail a clinician would actually experience.
- Record: GPU model, quantisation, Ollama version, model digest, concurrent load (none), and whether the machine was otherwise idle.

### 7.3 Deployment caveat

All measurements are taken on the local RTX 4070 Ti SUPER. RunPod figures will differ. If a RunPod dry run happens before the thesis is finalised, record a small comparison set there; otherwise state the hardware explicitly and do not generalise.

---

## 8. Step breakdown

Individually gated steps are marked **[G]** — each requires real command output reviewed before the next begins. Unmarked steps may be batched.

| # | Step | Touches frozen code | Gate |
|---|---|---|---|
| 0 | Verification pass: confirm `ContextBuilder` settings injection, disclaimer assembly point, live-path latency stages, test-set purity re-run | No (read-only) | **[G]** |
| 1 | Config additions: `EVIDENCE_MODE`, disclaimer constants, generation parameters | No (additive) | |
| 2 | Disclaimer removal from LLM schema (`prompt_builder.py`, `structural_validator.py`, assembly point) | **Yes** | **[G]** |
| 3 | 30-case smoke run — zero parse failures required | No | **[G]** |
| 4 | Generation parameters wired through `OllamaClient` | **Yes** | **[G]** |
| 5 | Determinism verification (§4.1) | No | **[G]** |
| 6 | `ContextBuilder` evidence-mode branching | **Yes** | **[G]** |
| 7 | Unit tests for all three modes + updated disclaimer tests | No | |
| 8 | Harness `--arm` flag, arm recorded in output | No | |
| 9 | Pilot run, n=100 × 3 arms | No | **[G]** |
| 10 | Precision computation + extension decision | No | **[G]** |
| 11 | Full run (if extending) | No | |
| 12 | Scoring + paired bootstrap + failure-rate parity | No | **[G]** |
| 13 | Latency instrumentation | **Yes** (additive) | **[G]** |
| 14 | Latency measurement + P50/P95 | No | |
| 15 | `evaluation_config.json` extension, dev log entry | No | |

Full regression (Phase 4 through Phase 21) after steps 2, 4, 6, and 13.

---

## 9. Outputs

```
ml/outputs/evaluation/ablation/
    per_case_results_arm_empty.csv
    per_case_results_arm_labels_only.csv
    per_case_results_arm_full.csv
    paired_differences.csv
    ablation_bootstrap_summary.csv
    failure_rate_by_arm.csv
ml/outputs/evaluation/latency/
    per_stage_timings.csv
    latency_summary.csv
evaluation_config.json   (extended with a metrics_ablation block)
```

`evaluation_config.json` must record, for each arm: the exact `EVIDENCE_MODE`, all generation parameters, the model digest, the case list seed, the determinism-check outcome, and the pre-registered primary endpoint **as stated before the run**.

---

## 10. Risks

| # | Risk | Mitigation |
|---|---|---|
| 1 | Arm A fails structurally at a high rate (too little context to produce valid JSON) | Expected; recorded as a finding, not a bug. If Arm A's failure rate makes it uninterpretable, RQ2 is reported as not answerable and RQ1 — the primary question — proceeds unaffected |
| 2 | Determinism check fails (§4.1) | Within-arm variance quantified and reported alongside between-arm difference; conclusions scoped accordingly |
| 3 | Sequential arms → GPU/model state drift between runs | Run arms back-to-back on an otherwise idle machine; record model digest per arm; report the ordering |
| 4 | Disclaimer removal breaks a frozen contract in an unanticipated place | Step 0 verification pass; full regression after Step 2; individually gated |
| 5 | Primary endpoint does not clear | Reported as a negative result. The thesis claim then narrows from "retrieval improves generation" to "retrieval was adopted on Phase 0 retrieval evidence; its end-to-end generation contribution was not confirmed at this sample size" — which is defensible, where an unreported null is not |
| 6 | Phase 21 competes with i18n commit, teammate testing, and RunPod dry run for calendar time | Sequencing decision required from the technical lead; see §11 |
| 7 | ~~Pinning generation parameters changes production output~~ | **Dissolved by the §4 revision** — production default is preserved unset. A unit test asserts the outbound payload is unchanged |
| 8 | Disclaimer template wording breaks the Explainability Assistant's ability to cite the agreement score | §3.7 condition 3: Phase 10 integration test re-run as a hard gate before proceeding |
| 9 | Rendered agreement value silently diverges from the real `VotedLabel.agreement` | §3.7 condition 2: direct value comparison on ≥5 cases, not string inspection |

---

## 11. Resolution of draft 1's open items

| # | Item | Resolution |
|---|---|---|
| 1 | Production parameter pinning | **Resolved.** §4 rewritten: capability added, default preserved unset, evaluation pins via environment override. Production behaviour unchanged. Adoption in production deferred to a separate post-defense decision |
| 2 | Disclaimer boilerplate assumption | **Resolved, and the assumption was false.** §3.2–3.5 rewritten: the field is case-specific (cites real `VotedLabel.agreement`) and is consumed by the Phase 10 Explainability Assistant. Static constant withdrawn; server-rendered parameterised template adopted |
| 3 | Sample-size wording | **Resolved.** §6.5 now states explicitly that no final N is pre-committed |

### 11.1 Remaining open item

**Defense date and available working days.** The step breakdown is roughly two working days of focused work plus two to four hours of compute, contending with the pending i18n commit, the teammate test cycle, and the RunPod dry run. Sequencing cannot be recommended without the date.

**The 3-arm design is frozen.** Dropping Arm A is a last-resort reduction available only if the calendar genuinely forces it — not a convenience choice made to save compute. The full evidence ladder (no evidence → labels only → labels plus text) is methodologically stronger than RQ1 alone, and RQ2 is a real question, not padding.

Should the calendar force the reduction, the documented fallback is **B vs C only**: this preserves RQ1 and the pre-registered primary endpoint intact, cuts compute by a third, and removes the no-evidence fallback (§3.5) from the critical path. RQ2 would then be reported as not attempted rather than attempted and abandoned. Invoking this fallback requires an explicit, recorded decision — it is not a default.

### 11.2 Freeze status

Items 1–3 are resolved in this revision. The remaining item is a scheduling decision, not an architectural one, and does not block freezing.

**FROZEN.** Approved with §3.2–§3.7 exactly as revised — the substantive architectural correction from draft 1, which received fresh sign-off rather than inheriting draft 1's approval. The 3-arm design is frozen as specified.

---

*Document version: draft 2 — FROZEN. Implementation proceeds through §8's gated sequence from Step 0. Any deviation requires an explicit unfreeze and a recorded reason.*
