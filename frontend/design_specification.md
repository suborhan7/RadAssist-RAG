# RadAssist-RAG — Design Specification

**Version** 2.2 (canonical) · **Status** Frozen for implementation · **Date** 17 July 2026
**Repository path** `docs/design/design_specification.md`

**This document supersedes and replaces** `ui_specification.md` v1.0, `design_review_v2.md` v2.0, and `design_audit_v2.md`. Those three have been deleted. Where they disagreed, this document is correct. **This is the single source of truth for frontend implementation, backend integration, and the thesis UI chapter.**

**Companion artifact:** `radassist-v2-final.html` — 23 high-fidelity screens, built from the tokens in §6. The mockup is normative for layout; this document is normative for everything else.

---

## Contents

1. Product vision
2. Design principles
3. Information architecture
4. Navigation
5. User flows
6. Design system
7. Component specifications
8. Screen specifications
9. Accessibility
10. Interaction patterns
11. Backend requirements affecting the UI
12. Key decisions and rationale
13. Implementation notes and phasing
14. Future roadmap *(not in scope)*
15. Corrections to prior documents
16. Frozen

---

## 1. Product vision

RadAssist-RAG is an **AI-assisted chest X-ray reporting workspace** for the Bangladeshi clinical context. A radiologist uploads a chest radiograph; the system masks identifying information, retrieves similar prior cases from the hospital archive, aggregates what those cases agree on, and drafts a structured bilingual report grounded in that evidence. The radiologist interrogates it, edits it, and signs it.

**The AI drafts. The doctor signs.** This is enforced by a state machine, not by a disclaimer.

The product is judged on two axes that pull against each other:

- **Clinical plausibility** — a radiologist should be able to sit down and work. Density, speed, keyboard reach, no ceremony.
- **Research legibility** — an examiner should *see* the contributions without being told. Retrieval evidence, PHI masking, deterministic comparison, and human oversight must be visible, not described.

Most student projects fail the first. Most clinical products would fail the second, because they hide the machinery. The design satisfies both without turning the interface into a demonstration of itself.

**Tagline:** *Grounded in cases. Signed by you.*

---

## 2. Design principles

**P1 — The image is the darkest thing on screen.** Application chrome is light paper. Imaging surfaces are true black wells. No other element uses a near-black fill. This is the visual signature and it is clinically motivated: contrast draws the eye to the radiograph first.

**P2 — Colour means something.** Red is a new finding or an error. Amber is unreviewed AI output, a persistent finding, or a warning. Green is resolved, normal, or online. Steel is retrieved evidence — and brand. No decorative colour exists. A user who learns the Comparison Workspace has already learned the status system.

**P3 — Machine output is typographically marked.** Anything the system generated or measured — patient codes, similarity scores, timings, model names — is set in mono. Anything a human wrote or will sign is set in sans. Provenance is readable at a distance, without labels.

**P4 — Density where data lives, air where decisions happen.** Tables and evidence lists are tight. The report body, the finalize control, and the review banner get room. Uniform spacing is a tell of a template.

**P5 — The AI never gets the last word, and the interface says so structurally.** Not through a disclaimer nobody reads, but through the status machine: no report reaches Final without a human transition, enforced server-side.

**P6 — Never overstate the system.** If a figure is a rule over retrieval similarity, the interface says so. If a narrative is written by an LLM from a deterministic diff, the interface attributes both halves. Overclaiming is the fastest way to lose an examiner and the only way to hurt a patient.

---

## 3. Information architecture

### 3.1 The ownership model

One word — "workspace" — was doing two jobs. They are separated:

| | Scope | Rule |
|---|---|---|
| **Your workspace** | Dashboard, drafts, reports, history, activity, settings | **Absolute isolation.** No doctor reads another's work. |
| **The hospital registry** | Patients and their studies | **Institutional.** Discoverable by name/ID. Other doctors' reports open **read-only**. Access is **logged**. |

**Reports are owned. Patients are not.** Another doctor may view, compare, and reference a report; never edit, delete, finalize, or overwrite it. A new examination always produces a new report owned by the doctor who performed it.

### 3.2 Flow

```
Public landing
   └─> Login
        └─> Dashboard ────────────┐
             ├─> My Reports       │
             ├─> Drafts           │
             ├─> Patients ────────┤
             │     └─> Register   │
             ├─> Studies ─────────┤
             └─> Patient Profile ─┘   (clinical hub)
                   ├─> New Examination
                   │     ├─ 1 Upload  (PHI masking)
                   │     ├─ 2 Retrieval
                   │     ├─ 3 Questionnaire (optional)
                   │     └─ 4 Generate
                   │            └─> Radiologist Workspace
                   │                  ├─> Explainability (drawer)
                   │                  └─> Comparison Workspace
                   └─> Comparison Workspace (from any timeline entry)
```

### 3.3 Why Patient Profile is the clinical hub

A study is not a free-floating object with a patient attribute. The patient is durable; studies hang off them in time order. Making the Profile the hub means **the timeline is the navigation** — the examiner meets the longitudinal-comparison novelty as structure rather than as a feature behind a button.

It also matches the work. A radiologist does not think *"I have an X-ray, whose is it?"* They think *"this patient is back, what changed?"*

---

## 4. Navigation

```
MY WORKSPACE
  Dashboard
  My reports
  Drafts              [3]
HOSPITAL REGISTRY
  Patients
  Studies
SETTINGS
  Profile
  Workspace
  System
```

Eight items. **Two zone labels do the teaching:** everything above `HOSPITAL REGISTRY` is yours; everything below it is shared. The doctor's identity and a `Private workspace` chip pin the footer. A doctor learns the privacy model from navigation alone.

- Sidebar **240px**, collapses to a **64px icon rail** — automatically and non-negotiably — in the Radiologist Workspace and Comparison Workspace, where pixels belong to the image.
- Top bar **56px**: global search (code or name), breadcrumb, current-patient chip, doctor menu.
- `Drafts` is a **filtered view of My Reports** (`status IN (AI Draft, Under Review)`), not a second screen. It earns a nav item because a badge changes behaviour and a filter chip does not.

**Cut, with reasons** (see §12): Upload History · Clinical History · Notifications · Admin console.

---

## 5. User flows

**Primary — report a new study**
`Search patient → Profile → New examination → Upload (mask) → Retrieval → Questionnaire (skippable) → Generate → Workspace → interrogate → edit → Finalize → Export`

**Secondary — follow-up comparison**
`Profile → timeline entry → Compare → select prior (any) → read deterministic diff → accept narrative → back to Workspace`

**Tertiary — reference a colleague's report**
`Patients or Studies → open a study you don't own → read-only report → Compare with current` — access written to the patient's log.

**New doctor, first session**
`Login → empty Dashboard → Register patient OR Search registry → Profile → New examination`

---

## 6. Design system

### 6.1 Direction — "Paper & Lightbox"

The application is a lit room made of paper. Cool off-white canvas, white cards, hairline borders doing the work shadows would do in a consumer product. Into that room we cut **black wells**: the image viewers. The contrast between chrome and lightbox is the highest on screen, deliberately.

There is no dark theme, beyond the brief saying so: a dark UI would destroy the signature. **The lightbox is only special because nothing else is dark.**

### 6.2 Tokens — normative

**Zero hardcoded hex.** The only exception is the four values inside the synthetic radiograph SVG, which are image data. Every value below is a token; nothing else is permitted in a component.

```css
:root{
  /* neutrals */
  --paper:#F2F5F7; --surface:#FFFFFF; --sunken:#EAEFF3;
  --hairline:#E3E8ED; --hairline-strong:#BFC9D3;
  --ink:#0D1520; --ink-2:#54626F; --ink-3:#6E7C8A;

  /* brand */
  --steel:#0F5C87; --steel-hover:#0B486B; --brand-deep:#0A3D5C;

  /* semantic triads — tint / border / deep text */
  --steel-tint:#E7F0F6;    --steel-bd:#C5DCEA;    --steel-ink:#0B486B;
  --caution-bg:#FFFAEB;    --caution-bd:#F5D9A8;  --caution-ink:#8A5A22;
  --caution:#B54708;       --caution-fill:#F79009;
  --stable-bg:#ECFDF3;     --stable-bd:#B7E4C7;   --stable-ink:#22684A;
  --stable:#067647;
  --critical-bg:#FEF3F2;   --critical-bd:#F0C4BF; --critical-ink:#8C2018;
  --critical:#B42318;

  /* lightbox surface set */
  --lightbox:#08090B; --lightbox-chrome:#1C222B; --lightbox-bd:#2E3742;
  --lightbox-ink:#C9D3DD; --lightbox-ink-2:#98A6B4; --lightbox-ink-3:#6B7885;

  /* spacing — these three, nothing else */
  --pad-card:16px; --pad-tight:12px; --pad-page:24px;

  /* radius */
  --r-in:2px; --r-btn:4px; --r-card:6px; --r-modal:8px; --r-pill:999px;

  /* elevation = dismissibility */
  --e1:0 1px 2px rgba(13,21,32,.05);
  --e2:0 4px 12px rgba(13,21,32,.10);
  --e3:0 16px 40px rgba(13,21,32,.18);

  /* ownership */
  --hatch:rgba(133,147,160,.10);
}
```

**Every semantic colour is a triad — tint, border, deep text.** This is the rule the V1 system was missing, and its absence caused every banner in the product to invent its own border by hand. If you add a semantic, you add three values.

**Elevation maps to dismissibility.** Level 0 (border, no shadow) is content in the document — cards live here. `--e1` is sticky chrome. `--e2` is dismissible: popovers, menus. `--e3` is blocking: modals, drawers. **If it floats, you can get rid of it.** A user learns this without being told.

### 6.3 Spacing grid — normative

**4px base:** `0 · 2 · 4 · 8 · 12 · 16 · 20 · 24 · 32 · 40 · 48 · 56 · 64`. Nothing between. Per P4: tables and rails use `--pad-tight`; cards use `--pad-card`; pages use `--pad-page`.

### 6.4 Typography — normative

**IBM Plex Sans** (UI, headings, report body) · **IBM Plex Mono** (all machine-generated data) · **Noto Sans Bengali** (Bangla).

Plex was drawn for technical documentation and instrument interfaces — it reads as a medical device rather than a SaaS dashboard, and its mono companion is metrically related, so a table can mix a patient name and a patient code without the baseline breaking. Explicitly **not Inter**, which is the default that signals no decision was made.

| Role | Size / line | Weight | Tracking |
|---|---|---|---|
| Hero | 44 / 50 | 600 | `-0.025em` |
| Hero (≤1279px) | 32 / 38 | 600 | `-0.02em` |
| Display | 28 / 34 | 600 | `-0.02em` |
| H1 | 22 / 28 | 600 | `-0.015em` |
| H2 | 18 / 24 | 600 | `-0.01em` |
| H3 | 15 / 20 | 600 | `-0.005em` |
| Body | 14 / 21 | 400 | `0` |
| Report body | 15 / 26 | 400 | `0` |
| Report body (Bangla) | 15 / 29 | 400 | `0` |
| Small | 13 / 18 | 400 | `0` |
| Label | 12 / 16 | 500 | `+0.005em` |
| Eyebrow | 11 / 14 | 600 | `+0.06em` uppercase |
| Mono data | 13 / 18 | 400 | `0` tabular |
| Mono small | 11 / 14 | 500 | `0` tabular |

**Nothing below 11px exists.** Base is 14px, not 16: enterprise radiology is dense, and 16 would force scrolling in the evidence rail. The exception is report prose at 15/26 — the only continuous text a human reads word-by-word and signs under. Bangla gets 29 leading because conjuncts crowd at 26.

### 6.5 Grid and fixed dimensions

12 columns, 24px gutter, page padding `--pad-page`. Max content 1680px. Minimum supported **1366px**. Design target **1600px**.

| Element | Size |
|---|---|
| Sidebar | 240px · rail 64px |
| Top bar | 56px |
| Study context bar | 48px |
| Report column | 520px |
| Evidence rail | 360px · collapsed 44px |
| Explainability drawer | 460px |
| Viewer | flex, min 420px |
| Finalize bar | 64px |

Workspace at 1366: `64 + 420 + 520 + 360 = 1364`. Fits with 2px to spare, which is a coincidence rather than a design — so **below 1600px the evidence rail starts collapsed** and the viewer gets 776px. At 1920: viewer 976px.

### 6.6 Icons

**Lucide.** 16px in dense UI, 20px in nav and toolbars, `1.5` stroke, `currentColor`, never coloured independently of their label. Icon-only buttons require `aria-label` and a tooltip. No icon ships without a label or a tooltip — an icon-only interface is a memory test.

### 6.7 Brand

**Name:** `RadAssist-RAG`. Retained deliberately — it is in the repository, the development log, the P2 submission, and the thesis. A rename before submission buys nothing and risks inconsistency across documents an examiner reads side by side.

**Mark — an aperture onto a rib arc.** A rounded square (`--r-btn`) in `--lightbox`, containing three nested arcs in white. The innermost is solid — this study. The two outer arcs are progressively lighter — its retrieved neighbours.

- **It is the product.** The black square is the same lightbox on every screen. The logo is the UI's signature compressed to 16px, not decoration applied to it.
- **The rib arc is unmistakably chest radiography.** No stethoscope, no cross, no caduceus.
- **The nested arcs encode retrieval honestly** — one case plus its neighbours. It reads as a ribcage to anyone who doesn't ask, and as retrieval to anyone who does.
- **No AI cliché.** No node graph, no brain, no sparkle, no gradient orb. Those date a product to the month it was designed.
- **Degrades:** at 16px, a dark square with a light curve. Favicon uses a **single arc** — three mush at that size.

**Wordmark:** `RadAssist` in Plex Sans 600, `-RAG` in Plex Mono 400 at `--ink-3`. The technique in the machine face, the product in the human face.

---

## 7. Component specifications

| Component | Variants / states | Notes |
|---|---|---|
| Button | primary · secondary · ghost · danger; sm 28 / md 32 / lg 40; loading, disabled | One primary per view |
| Input / Select / Textarea | default, focus, error, disabled | Label above, error below, 32px (40 in forms) |
| StatusChip | draft · review · edited · final | §10.1 |
| OwnershipChip | you · other | Steel + check / neutral + name. **Text-based** |
| ServiceChip | online · degraded · offline | Dot + label + latency (mono) |
| AgreementBadge | strong · mixed · weak | Word + factors. Never a bare % |
| SimilarityBar | — | Bar + mono %, `--steel` fill. **No bar at 0** |
| EvidenceCard | collapsed · expanded · highlighted | Highlight fires from report hover |
| CitationMarker | — | Superscript mono + dotted underline |
| PatientIdentityBand | — | Persistent patient context |
| TimelineEntry | owned · read-only | Date, interval, modality, doctor, status, access |
| Stepper | 4 steps: done/current/todo | New Examination |
| PipelineProgress | per-stage, timed | Upload |
| Lightbox | viewer + toolbar | The only black surface |
| ReportSection | view · edit · regenerating | Hover affordances |
| DiffView | added · removed · unchanged | Edit tracking |
| FindingsDiffList | new · persistent · resolved | Comparison |
| ReviewBanner | caution · read-only · signed | Sticky, non-dismissible until state changes |
| ValidationList | error · warning | Gates Finalize |
| Drawer | 460px right, `--e3` | Explainability |
| Modal | 480 / 640, `--e3` | Confirmations only |
| Menu | `--e2` | Profile menu |
| Toast | success · error | 4s, bottom-right |
| EmptyState | — | Always contains the action that resolves it |
| Skeleton | — | Static `--sunken` blocks. **No shimmer** |

---

## 8. Screen specifications

23 screens, all built in `radassist-v2-final.html`. Layout there is normative.

### 8.1 Landing (public)

Hospital platform homepage, not a marketing site. Slim header · split hero (copy / lightbox) · pipeline strip · research footer.

**The hero shows proof, not stats.** Under the headline sits **one real grounded sentence** — the dotted underline and the `CXR-2117 · 97.4%` citation chip, exactly as it appears in the Workspace. A three-stat row was rejected: it is the shape every AI startup ships, and a page that claims "every statement traces to a retrieved case" and then shows none is asserting rather than demonstrating. One line survives beneath it: **"0 reports have ever been finalised without a radiologist"** — a constraint, not a brag.

**Pipeline strip:** seven stages — `Chest X-ray → PHI protection → BiomedCLIP → ChromaDB → Similar cases → AI draft → Radiologist review`. The seventh node carries **1.6× the width** of the others and the only tint. Six machine stages and one person; the layout argues what the copy says.

**Responsive:** stacks below **1280px** — hero full width, radiograph a 240px band beneath, pipeline scrolls horizontally, hero type drops to 32/38. This is the one screen likely to be projected at an odd aspect during a defence.

### 8.2 Login

Split: lightbox left, form right. **Service status strip** — FastAPI, Ollama, ChromaDB, GPU — before authentication, because in a live demo the failure mode is a cold Ollama, and without this strip the room watches a spinner and concludes the software is broken.

Errors are specific and do not apologise: *"Email or password is incorrect."* Never *"Something went wrong."*

### 8.3 Dashboard

**The work leads.** The greeting is Small/13 in `--ink-2`; the H1 is **"3 reports awaiting your review"** with an `Open oldest` action inline and the age beneath. Empty queue → **"Your queue is clear."**

A greeting as the largest text on screen carries zero information. PowerScribe opens to a worklist, not a welcome.

Four tiles: Your examinations today · Patients you've reported (`38 — of 142 in the registry`) · Reports you've generated · Awaiting your review. Then: your recent activity table, quick actions, **Registry card**, system status.

**Zero charts.** Test applied: *does this change what the doctor does next?* Nothing passed. The Registry card sitting beside your private counts — `38 of 142` — teaches the ownership model through arithmetic, every morning. That is what makes the screen alive, not motion.

### 8.4 My reports / Drafts

Doctor-scoped. Status filter chips, date range, agreement filter, patient filter. Columns: Patient · Study date · Status · **Agreement** · Edited · Generated · Language. Footer: *"median generation 6.1s · median edit distance 12%"* — evaluation data collected as a by-product of normal work.

### 8.5 Patients (registry)

Shared registry. Scope filter (`My patients 38` / `Whole registry 142`), search by **Patient ID** (exact) or **Name + DOB** (fuzzy name, exact DOB).

Results split into two zones: **in your workspace**, then **elsewhere in the registry** behind a steel band explaining read-only access and logging. This band is the duplicate-record prevention: searching the whole registry before registering is how you avoid two Nusrat Jahans.

Name+DOB is a compound key because DOB disambiguates the four Md. Rahmans, and opening the wrong chart is a real harm with a real mechanism. ≥5 name matches → *"Add a date of birth to narrow this."*

### 8.6 Register patient

Modal, 480px. Name · DOB · Sex · Phone (optional) · Hospital MRN (optional). **Patient ID is server-generated** in-transaction: `RA-{YYYY}-{NNNNNN}`. Never client-generated, never derived from name or DOB — that would leak PHI into an identifier appearing in logs and URLs.

**The PHI question an examiner will ask:** *"You mask PHI in the image but store the patient's name?"* Yes, and the distinction is the point. The database is the **authorised store** — access-controlled, never embedded, never indexed. The image is the **leak path**: pixels containing a name flow into BiomedCLIP, into ChromaDB as a vector, into an index similarity-search can traverse. Registration is what makes masking safe: identity is captured in the controlled channel, so the uncontrolled one can be scrubbed without losing it. This is why OCR-based patient identification is rejected outright.

### 8.7 Patient profile — clinical hub

Identity band with ownership summary (`3 reported by you · 1 by Dr. K. Rahman`). Left rail: summary, **access log**. Main: **history timeline**, newest first.

Each entry: date · time · **interval since previous** (`62 days`) · modality · labels · ownership chip · status · agreement · generation time · actions. Entries you don't own are hatched, read-only, and still **comparable**.

**The printed interval is the argument.** It is the reason longitudinal comparison exists, and printing it makes the contribution legible before anything is clicked.

### 8.8 Studies (registry)

Hospital-wide study list — the My Reports table with the owner filter removed. Columns include **Reporting doctor** and **Access** (`Editable` / `Read-only`). Real PACS furniture, near-zero cost.

### 8.9 Upload + PHI

Stepper · dropzone → preview · patient rail · **pipeline progress** with five timed stages: Upload · Image validation · PHI detection & masking · BiomedCLIP embedding · ChromaDB retrieval.

**The PHI reveal slider** is the highest-value interaction in the product. After masking, the preview shows the masked image with a draggable divider; drag left to reveal the original beneath, masked regions outlined in `--steel` and labelled. PHI masking is a real contribution that is by nature invisible — a scrubbed image looks like an image. The slider makes it demonstrable in two seconds, using the examiner's own hand.

Constraint, printed on the slider: *"Original shown from this session only. Not stored."* This is literally true — see §11 B7.

Failures are actionable: *"This image is 480×512. Chest X-rays below 512×512 retrieve poorly — upload a higher-resolution copy."*

### 8.10 Retrieval

**Evidence summary leads; the case list follows.** Aggregated agreement — *"Cardiomegaly, 4 of 5 cases"* — is what separates this from "retrieve top-K, paste into prompt." Doctors think in findings; cases are the citation, not the claim.

K selector (3/5/10) re-queries ChromaDB only — no re-embedding — and the latency figure updates, demonstrating the caching architecture without a word.

Decision hint: high agreement → questionnaire optional, `Skip` offered at equal weight. Low agreement → *"Retrieved cases disagree. Clinical history will improve this report."* and Skip drops to ghost. Threshold is configuration, never a literal.

### 8.11 Questionnaire

Optional, always. Label-driven question sets. The intro states **which retrieved labels produced these questions** — the form explains itself and demonstrates that retrieval feeds context.

**Every question offers "Unknown."** A forced Yes/No manufactures data. The Context Builder must distinguish *"no"* from *"not asked"*; collapsing them corrupts the evidence the LLM reasons over.

### 8.12 Radiologist Workspace ★

Rail nav · study context bar · **Lightbox (flex) · Report (520) · Evidence rail (360)** · finalize bar.

**Lightbox:** true black. Vertical toolbar: zoom, fit, 1:1, invert, window/level, pan, reset, PHI mask overlay. Prior-study thumbnails bottom-left. Window/level is not decoration — it is how a radiologist looks at a chest film, and its absence is the first thing a clinical reviewer notices.

**Report as document,** not a stack of cards: continuous paper, hairline section rules, at the proportions of the PDF export. Hover reveals `Edit` / `Regenerate` per section. Regenerate re-runs **that section only**, streaming in place.

**Evidence citation — the signature interaction.** Grounded sentences carry a dotted `--steel` underline and a superscript mono marker. Hovering: the case card lifts to `--steel-tint`, scrolls into view, and its similarity bar pulses once. Hovering the card inverts it — every sentence it supports underlines at once. **The link runs both ways.**

This is the answer to *"how do I know the AI didn't make this up?"* — the doctor's own cursor is the proof. If one thing survives implementation, make it this.

**Uncited sentences render plain, and that is information.** An uncited clinical assertion is one to look at harder. Never fabricate citations for visual uniformity.

**Rail tabs:** Evidence · Agreement · Alternatives.

**Three columns, three registers:** the viewer is black and wordless; the report is paper and sans; the rail is paper, quieter, mono-heavy. A user knows which column they are in with peripheral vision.

### 8.13 Explainability

**A drawer, not a page.** Every question a doctor asks is *about* something on screen; navigating away to ask it is a design error. The drawer expands the rail to 460px and keeps image and report visible, so answers can highlight the exact sentence they refer to.

**Why it does not look like ChatGPT:** no bubbles, no avatars, no left/right alternation, no typing dots. The question is a bold rule; the answer is plain prose in the document register; evidence chips sit beneath as citations. It reads like a marginal annotation on a report — which is what it is. Bubbles imply chat, chat implies conversation, conversation implies the model is a colleague. It is an index over five documents, and the typography should say so.

Grounding notice, non-dismissible: *"Answers are grounded in the retrieved cases and this report. The assistant cannot introduce new findings."* The "Why not TB?" answer honours it: *"This is an absence of supporting evidence, not an exclusion."* An LLM asked that question will happily produce a confident exclusion. The prompt must forbid it.

### 8.14 Comparison Workspace ★

**Previous (flex) · Interval diff (320) · Current (flex)**, narrative below. Study pickers accept **any** pair from the timeline; interval recomputes live. Linked viewers (`⛓`) synchronise zoom and pan — the single behaviour that makes this feel like PACS rather than two images side by side.

**The diff is the spine, and its authorship is public:**
- Under the diff: *"Computed by ComparisonService · Deterministic"*
- Under the narrative: *"Narrative generated by llama3:8b from the deterministic diff above."*

**The LLM is not deciding what changed. It is writing down what the diff already decided.** When an examiner asks how you stop the model hallucinating interval change, the answer is on the screen: it structurally cannot, because it never computes the change.

New/Persistent/Resolved use `--critical`/`--caution`/`--stable` **with text labels**, never colour alone.

### 8.15 Read-only report

Neutral banner instead of amber: *"Reported and signed by Dr. K. Rahman. You can read it and compare against it. Your access has been recorded."* Edit, regenerate, and finalise disabled. Signature block. `Compare with current study` remains primary — that is the clinical point.

### 8.16 Settings · Profile / Workspace / System

**Profile:** identity, BMDC number (*"Recorded as entered. Not verified against the BMDC registry"* — honest), and a **live signature preview** showing exactly how the block appears on a finalised report.

**Workspace:** per-doctor defaults — K, language, questionnaire skip, rail state, export format. Thresholds shown **read-only** with: *"These are rules over retrieval similarity, not calibrated probabilities."*

**System:** service health, index stats, and **storage & privacy** — `Masked images stored: 412` / **`Original images stored: 0`** beside the statement: *"The system cannot disclose unmasked PHI from storage, because unmasked PHI is never stored."* Quietly the strongest trust artifact in the product.

### 8.17 Empty workspace

*"Your workspace is empty. Register a patient, or find someone already in the registry. Patients other doctors have reported stay out of your workspace until you report on them yourself."*

The only moment a doctor is receptive to learning the ownership model.

---

## 9. Accessibility

- **WCAG 2.1 AA** for all clinical text. `--ink` on `--surface` 16.8:1; `--ink-2` 6.4:1; `--ink-3` 4.6:1 at 12px; `--steel` 6.5:1.
- **Nothing below 11px.** The 9px thumbnail labels were removed — below the legibility floor on the declared hardware, where contrast ratios are meaningless anyway.
- **Focus visible everywhere:** `2px --steel`, `2px` offset, tokenised, never removed, never animated. A focus ring that fades is a focus ring you miss.
- **Full keyboard operation of the primary path:** search → open patient → new exam → upload → generate → edit → finalize.
- **Shortcuts (Workspace):** `E` edit · `R` regenerate · `V` evidence rail · `X` explain · `L` language · `Ctrl+S` save · `Ctrl+Z` undo within section · `?` shortcuts.
- **No information is carried by colour alone.** The comparison diff is labelled New/Persistent/Resolved in text; a red/green-blind reader loses nothing. Ownership is carried by a **text chip**; the hatch at `--hatch` (10% — 4.5% was invisible and the redundant-cue claim it supported was false) is a pre-attentive scanning aid on top, not the mechanism.
- **Landmarks** and `aria-live="polite"` on pipeline progress, generation status, toasts.
- **Alt text** describes the study (`"Chest X-ray, PA projection, 2026-07-14"`), never the AI's interpretation.
- **Minimum hit target** 32×32.
- `prefers-reduced-motion: reduce` → all durations 1ms, streaming reveal disabled (text appears complete).

### 9.1 Responsive

| Range | Behaviour |
|---|---|
| ≥1600px | Full layout, evidence rail open |
| 1366–1599 | Rail starts collapsed in Workspace |
| 1280–1365 | Landing stacks; app screens hold |
| 1024–1279 | Workspace and Comparison → tabs (Image / Report / Evidence). Usable, not intended |
| <1024 | Dashboard, Patients, Profile read-only. Workspace and Comparison: *"Reporting requires a display of at least 1024px. Open this study on a workstation."* |

Refusing to render a diagnostic viewer on a phone is a **safety position, not a limitation**. A 6" screen cannot support radiological interpretation, and pretending otherwise would be the design failure.

---

## 10. Interaction patterns

### 10.1 Report status machine

```
AI Draft ──▶ Under Review ──▶ Doctor Edited ──▶ Final
```

| Status | Chip | Set by |
|---|---|---|
| AI Draft | `--caution-bg` | System, on generation |
| Under Review | `--steel-tint` | System, on Workspace open >5s |
| Doctor Edited | `--steel-tint` + ✎ | System, first keystroke |
| Final | `--stable-bg` + ✓ | **Doctor, explicitly** |

`Final` is terminal, locks all sections, requires validation to pass, and is **enforced server-side** — a client cannot post a Final report that never passed through a human. Every transition is timestamped and attributed.

**Honest limitation for the thesis:** `Under Review` fires on a 5-second timer. A doctor can open, wait, and finalise without reading. No interface prevents that, and a forced dwell gate would only train people to work around it. **The status machine records workflow state, not attention.** Claiming otherwise would violate P6.

### 10.2 Evidence agreement

Never a bare percentage. **Strong · Mixed · Weak**, plus factors:

```
EVIDENCE AGREEMENT              Strong
Because  4 of 5 retrieved cases agree on the primary finding
         Top-1 similarity            97.4%
         Mean similarity (K=5)       94.1%
         Clinical history provided   Yes

Measures agreement among retrieved cases.
Not a probability that the report is correct.
```

The measure is named for what it measures, so the closing line is a **definition rather than a disclaimer** — and the calibration objection disappears, because nothing claims calibration.

### 10.3 Alternatives in retrieved evidence

```
Present in the retrieved set          Not present in the retrieved set
  Cardiomegaly       4 of 5            Tuberculosis        0 of 5
  Emphysema          2 of 5            Pleural effusion    0 of 5
  Granuloma          1 of 5            Pneumonia           0 of 5

Absence here means no retrieved case carried the label. It is not an exclusion.
```

**The "not present" block is the valuable half**, and a ranked confidence list destroys it. *"TB: 0 of 5"* is a fact. *"Tuberculosis — Low"* is a claim the system cannot support. No bar renders at 0.

### 10.4 Bilingual reporting — stated precisely

Toggle `[EN | বাং]` in the study context bar.

- Switching **never** re-runs PHI masking, BiomedCLIP, or ChromaDB.
- Switching **does** invoke the LLM once in translation mode.
- Result cached against `(session, language)`. Subsequent switches instant.

Say it this way in the thesis. "Switching without regenerating" is imprecise — a translation call happens. What does not happen is the expensive half of the pipeline, and *that* is the optimisation worth claiming. First switch shows *"Translating report…"* (~2s); the response-time panel shows both figures.

Clinical terms stay in English inside Bangla prose — that is how Bangladeshi clinicians write, and translating "cardiomegaly" reduces precision rather than increasing accessibility.

**Known limitation (Future Work):** editing English after translating invalidates the cache → *"The Bangla version is out of date. Retranslate."*

### 10.5 Doctor edit tracking

`Changes vs AI draft` toggle. Word-level diff; header: **"14% of the AI draft was edited · 3 of 7 sections changed."** Evaluation data collected while the doctor simply does their job.

### 10.6 Response time

Collapsed as `6.06s ▾`; expanded, a per-stage breakdown in mono. **The one visualization in the product that earns its place** — diagnostic, per-study, answers "why was that slow?"

### 10.7 Validation

| Check | Severity |
|---|---|
| Findings empty | Error |
| Impression empty | Error |
| Clinical history empty | Warning |
| Recommendation empty | Warning |
| Term absent from retrieved evidence | Warning — *"'consolidation' does not appear in any retrieved case. Verify before finalising."* |

The last is the ResponseValidator taxonomy-term hallucination heuristic, surfaced. It is one of the more original things in the backend and V1 gave it no UI.

### 10.8 Micro-interactions

All functional, all ≤200ms, all respect reduced motion.

| Interaction | Spec |
|---|---|
| Hover | `background` 120ms `ease-out`. No lift, no scale, no shadow bloom |
| Focus | Instant, never animated |
| Nav | Instant, `--steel-tint` fill. No sliding indicator |
| Citation hover | Card → `--steel-tint` 120ms + bar pulse (scaleX 1→1.02→1, 300ms). **The one flourish**, earned because it confirms a cross-panel link the user cannot otherwise see land |
| Pipeline stage | Spinner → check 150ms; elapsed counts up live in mono. **The signature motion** — the only place waiting is honest work |
| Generation | Per token. **No typewriter, no cursor.** Findings streams first |
| Section regenerate | Target only → `--sunken` wash → replace → wash out 200ms. The rest never moves |
| Rail / drawer | `transform` 200ms `cubic-bezier(.2,0,0,1)`. **Never `width`** — width reflows the report mid-read |
| Skeletons | Static `--sunken`. **No shimmer** — an AI-startup tell that implies speed the LLM does not have |
| Toast | Slide-up 180ms, 4s dwell |
| Autosave | `Saved 09:44` in the finalize bar. Silent, always present |

---

## 11. Backend requirements affecting the UI

| # | Requirement | Notes |
|---|---|---|
| B1 | **Auth**: `doctors` table, Argon2, JWT (httpOnly), login/refresh/logout | |
| B2 | **Ownership**: `doctor_id` on studies/reports. Gates **writes and report-reads**. Patient registry **read-unfiltered**. Enforced at the **repository layer** | ⚠️ See below |
| B3 | **Patient ID**: `RA-{YYYY}-{NNNNNN}`, server-side, in-transaction | |
| B4 | **Patient search**: exact by code; fuzzy name + exact DOB; normalized-name column + index | |
| B5 | **Dashboard aggregates**: doctor-scoped summary + activity | |
| B6 | **Service health**: FastAPI, Ollama (+model), ChromaDB (+count), GPU (+VRAM) | |
| B7 | **Persist masked image + 128px thumbnail per study. Never persist the original.** | ⚠️ **P1 prerequisite** |
| B8 | **Arbitrary-pair comparison**: `GET /comparison?previous={id}&current={id}` | |
| B9 | **Immutable AI draft snapshot** + edit distance | |
| B10 | **Per-sentence citation map** in the report payload | |
| B11 | **Timing instrumentation** per stage | |
| B12 | **Translation cache** keyed `(session, language)` | |
| B13 | **Status transitions validated server-side** + audit rows | |
| B14 | **Config**: retrieval/agreement thresholds, default K → settings. No literals in components | |
| B15 | **`access_log`**: `doctor_id · patient_id · study_id · action · at`. Written on any cross-owner read | |
| B16 | **Doctor profile**: designation, BMDC, institution, signature block | |
| B17 | **Per-doctor workspace settings** | |
| B18 | **`GET /reports`** — doctor-scoped; filters: status, date, agreement, language | |
| B19 | **`GET /studies`** — registry-wide, returns owner | |
| B20 | Report payload returns **`agreement`** (strong/mixed/weak) + factors, replacing `confidence` | |
| B21 | Retrieval payload returns **the full label taxonomy including zero counts** | ⚠️ See below |

**Three that are easy to get wrong:**

**B2 is the dangerous one.** Doctor scoping must live in the **repository layer** as a mandatory filter, not be added per service method. One service that forgets it is a cross-tenant leak, and nobody catches a missing `WHERE` in review. One place to get right, one place to test. Note this is *less* filtering than strict isolation — fewer places to leak.

**B7 has a subtlety.** Mask in memory; persist only the masked image. The reveal slider reads the session buffer and dies with the session. Persisting the original would make masking theatre — the unmasked pixels would sit on disk and the privacy contribution collapses under one question.

**B21 requires absence.** The "not present in the retrieved set" block needs counts for the **full taxonomy**, not just the labels retrieval found. A payload listing only what it retrieved cannot render the most valuable half of that panel.

**Migrations:** B1/B2 alter pre-existing tables. SQLite has no `ALTER TABLE ADD CONSTRAINT` — **Alembic batch mode** required, as this project already hit once.

---

## 12. Key decisions and rationale

**Patients are institutional; doctors own their work.** Strict per-doctor patient ownership breaks longitudinal comparison — the thesis's second-most-important screen. A patient registered by Dr. Karim in January and seen by Dr. Borhan in July becomes invisible, gets re-registered, and her four priors vanish. Duplicate patient records are one of the best-documented harms in health IT. It also misreads the reference products: PowerScribe and Sectra scope the *worklist*, not the *patient*. And it is worst in exactly the setting this thesis argues for — rotating clinicians, scarce radiologists. **The UX argument settles it:** strict isolation is invisible (an absent patient looks identical to a nonexistent one), while ownership is highly visible and teaches the boundary on every screen.

**Upload History cut.** Every upload produces a report; it was My Reports sorted differently. Two nav items for one set of rows is a tax paid on every navigation, forever, for a sort order.

**Clinical History cut from nav.** It is a property of a patient, not a collection. At hospital scope it implies a browser of everyone's clinical history — unusable, and a privacy liability if it existed.

**Notifications cut.** Every notification here reduces to *"you have unfinished work"* — which the Drafts badge already says, permanently, without a read/unread model or a delivery policy. *"Dr. X viewed your report"* is surveillance-flavoured and would fire constantly under a shared registry. **The badge is the notification.**

**No admin role.** The access log is on the Patient Profile, visible to any doctor treating that patient. Transparency to the treating clinician is a *stronger* privacy property than transparency to an administrator, and costs zero new roles. A hospital-wide view later is a `SELECT`, not an application tier.

**Confidence → Evidence agreement.** Keeping "confidence" implies a calibrated probability of diagnostic correctness; it is a rule over cosine similarity. Dropping it entirely loses the scan signal a busy radiologist needs. Renaming the measure to what it measures does both jobs and turns the caveat into a definition.

**Differential kept, epistemics fixed.** The panel was never the problem; the claim was. Label counts from retrieved evidence are factual and answer the real question — *what else is in the neighbourhood?* — without pretending to rank hypotheses.

**Evidence as a persistent rail, not an accordion.** Clinically the brief was right that evidence is subordinate. But an accordion closed by default hides the strongest thing the project does. Resolution: narrower, quieter, no black — subordinate — but never invisible. The citation markers are the real mechanism; the rail is where evidence *lives*, the markers are how it gets *used*.

**Report as a document, not cards.** The export must match the screen, and a radiologist's mental model of a report is a signed page. **Risk acknowledged:** users know cards are editable and paper is not. Mitigation: a one-time coach mark on the Findings header — *"Hover any section to edit or regenerate"* — dismissed forever on first edit. **If usability testing shows users still miss it, this decision loses and sections become cards.** The signature is not worth a broken primary action.

**Evidence rail may still be ignored.** Doctors under time pressure read the impression and sign. Persistent-but-unread is not better than an accordion; it just costs 360px. **Instrument it** — rail-open rate and citation-hover rate are cheap to log, and *"did making evidence visible change reading behaviour?"* is a publishable question.

---

## 13. Implementation notes and phasing

| Phase | Contents | Gate |
|---|---|---|
| **P0** | Design system: **§6.2 tokens complete**, type, Lucide, primitives. `/dev/kitchen-sink` route | **Zero hardcoded hex. Zero off-grid spacing. Zero off-scale type.** Automate this check in CI — it is a grep |
| **P1** | B1, B2, B6, B7. Landing, Login, Dashboard | Two seeded doctors see only their own work. **Security gate, not a UI gate** |
| **P2** | B3, B4, B5, B15. Patients, Register, Profile, Studies | Register → search → open profile on real data |
| **P3** | Upload, Retrieval, Questionnaire, PHI reveal slider | Real terminal output, not assumed |
| **P4** | **Workspace.** B10, B11, B13, B14, B20, B21. Citation linkage | Usable end-to-end. Nothing reaches Final without a human |
| **P5** | Explainability, B12, §10.2–10.7 | Explain answers cite. Language switch does not re-retrieve |
| **P6** | **Comparison.** B8, B9 | Any-pair comparison. Provenance notes present |
| **P7** | My Reports, Drafts, Settings ×3, B16–B19 | |
| **P8** | A11y audit, keyboard pass, 1366px pass, **skeletons**, empty/error/stale states, coach marks | AA on clinical text. Primary path fully keyboard-operable |

**P4 and P6 are the screens the thesis is judged on.** If the schedule compresses, compress P2 and P7. **Never P4 or P6.**

Every phase ends as this project's phases always have: real execution output, a commit, and a `development_log.md` entry with its *"How to Write This in Your Thesis"* section. **Chapter 3's UI section should be assembled from those entries, not written from memory in February.**

### 13.1 The two highest-value non-code tasks

**Seed the demo with four doctors and cross-owned studies.** This is the single highest-value item in the project and it is a seed script. Without it the ownership model, the read-only report, and the access log never appear on screen — three screens of work stay invisible to the examiner. Nusrat Jahan's 12 May study **must** belong to someone else.

**Rehearse the correction beat.** Every screen shows the happy path. There is no moment where the AI is wrong and the doctor fixes it — and that is the entire thesis. The parts are already built:

> The draft says *"Emphysematous changes are noted."* Validation fires: **"'Emphysematous' appears in 2 of 5 retrieved cases. Verify before finalising."** The doctor hovers the citation, sees only two weak cases support it, checks Agreement (`Mixed`), edits the sentence, and signs.

Thirty seconds. Hallucination heuristic + evidence rail + agreement reframe + human-in-the-loop + status machine, one continuous move, **zero new code**. It is the difference between *"the AI wrote a report"* and *"the system caught its own overreach and the doctor stayed in charge."*

### 13.2 Demo hygiene

- **Confirm the demo display is ≥1600px** before the defence, not during it.
- **Warm Ollama** before presenting. The login service strip exists so the room can see this.
- **Findings must stream first.** Never let the screen sit still for six seconds in front of a committee.

### 13.3 The remaining gap to commercial

Not polish on the happy path — **the in-between states.** Every screen here is perfectly populated. Commercial products spend roughly a third of their UI on loading, empty, error, partial, stale, and denied. That is the clearest tell separating student work from shipped software, and an examiner who has used clinical software will feel it in thirty seconds without naming it.

Minimum set, all achievable in P8:
1. **Skeletons for retrieval and generation.** Not spinners. The shape arrives before the content.
2. **Error states with a way out:** *"Ollama is not responding. The image and retrieval are cached — retry generation without re-uploading."* True, because the session cache is real.
3. **Stale state** for the Bangla report after an English edit.
4. **Autosave indicator and section-level undo.** A radiologist who loses an edit loses trust permanently.

---

## 14. Future roadmap

**Explicitly out of scope for the thesis.** Listed to show scalability was considered, not to be built.

| | Item |
|---|---|
| Integration | DICOM support · PACS · HIS/EMR · HL7/FHIR |
| Workflow | Worklist assignment and load balancing · report handover/reassignment · request-access approvals |
| Clinical | Additional modalities (CT, MRI, ultrasound) · expanded disease taxonomy · true image explainability (Grad-CAM / attention heatmaps) |
| Platform | Multi-hospital deployment · cloud · mobile clinician app · admin audit console · analytics dashboard |
| AI | Voice dictation · active learning from doctor edits · MPI with merge/unmerge |
| Bilingual | Bangla review workflow · bilingual export · translation-consistency evaluation |

**True image explainability is deliberately deferred.** BiomedCLIP is not a localisation model; producing clinically meaningful heatmaps requires Grad-CAM, CAM, or an attention-based vision model. An inaccurate heatmap would mislead users and weaken the evaluation — the opposite of this project's purpose.

---

---

## 15. Corrections to prior documents

Recorded because P6 — *never overstate the system* — applies to the design team as much as to the model, and because the thesis must not inherit claims that were never true.

### 15.1 The design audit's measurements are withdrawn

`design_audit_v2.md` §1 published specific figures: *"126 occurrences across 10 off-grid values"*, *"16 distinct hardcoded hex, ten of them UI chrome"*, and token adoption of *"0 uses"*.

**Those figures are withdrawn. Do not cite them.**

They were produced by a scanner corrupted by shell quoting. Four subsequent scans of the same artifact returned four mutually contradictory censuses — `--pad-card` at 0 uses, then 2; sixteen hardcoded hex, then one. The delivered artifact also differed in size from the file that was built, indicating post-hoc transformation in transit. No quantitative claim about the mockups' internals should be treated as evidence.

### 15.2 The findings stand on authorship, not measurement

Every audit finding remains valid, established by having written the code rather than by having scanned it:

| Finding | Basis | Status |
|---|---|---|
| `--pad-*` and `--e1..3` declared but never wired to components | Authored in V3CSS; component CSS used literals | Fixed — §6.4, §6.5 |
| Semantic borders and deep-text typed as literals into banners | Authored | Fixed — §6.2 triads |
| `font-size:9px` on prior-study thumbnail labels | Authored | Fixed — 11px floor, §6.3 |
| Ownership hatch at `rgba(...,.045)` | Authored | Fixed — `--hatch` at `.10`, §9 |
| Dashboard hierarchy led with a greeting | Design judgment | Fixed — §8.2 |
| Landing breaks at 1024 (`1fr 620px` → 404px column) | Arithmetic | Fixed — stacks below 1280, §8.0 |

The correct remedy was identical either way: **wire the tokens up**. §6 is now the contract, and P0's gate (§13) enforces it.

### 15.3 Two claims retracted outright

**The ownership hatch was credited with work it did not do.** V1 §4.8 stated that `row--other` carried a redundant non-colour cue so a red/green-blind reader lost nothing. At 4.5% alpha on white it was effectively invisible — not a redundant cue but a rounding error. The accessibility property held anyway, because the ownership **chip is text** — but for a different reason than the one claimed. The hatch is now `.10` and performs the function it was credited with.

**The confidence surface was caveated instead of corrected.** V1 presented a rule over cosine similarity as "Confidence" and attached a disclaimer explaining that it was not a calibrated probability. A disclaimer doing the work a label should do is a design failure. Renaming the measure to **Evidence agreement** (§10.3) makes the sentence a definition rather than an apology.

### 15.4 Superseded documents

**Delete these. They contain contradictions, withdrawn measurements, and reversed decisions:**

- `ui_specification.md` v1.0
- `design_review_v2.md`
- `design_audit_v2.md`

This document is the only design record for frontend implementation, backend integration, and Chapter 3.

---

## 16. Frozen

Design is frozen. Workflow, information architecture, ownership model, navigation, design system, and screen inventory are final and should not be revisited.

Open questions from earlier revisions are all resolved: masked image persistence (§11 B7), confidence wording (§10.2), the differential panel (§10.3), navigation (§4), notifications and the admin console (§12).

**Begin P0.**

---

*RadAssist-RAG · Brac University · Department of Computer Science and Engineering · Supervisor: Md. Shahriar Rahman*
