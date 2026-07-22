"""
ml/evaluation/run_generation_eval.py
====================================================================
Phase 20 Step 6: real generation-quality evaluation. Drives the REAL
backend HTTP API end-to-end for each held-out test case --
POST /retrieve (real upload -> real PHI masking -> real BiomedCLIP
embedding -> real ChromaDB retrieval) then POST /generate-report (real
Ollama generation) -- the exact same path a doctor's browser uses.
Never imports backend internals directly, respecting this project's
frozen `ml/` <-> `backend/` boundary (phase20_generation_evaluation_
architecture.md Decision 3).

Sample: the real, verified-untouched test-split pool -- Step 1's hard
purity gate (index_contents strictly subset of train union validation,
zero test overlap, confirmed against the live ChromaDB collection AND
its source embedding cache independently) plus Step 2's eligibility
filter (has_frontal AND real findings_clean AND real impression_clean).
477 real eligible cases as of this phase's investigation, not the raw
595-study test split. Adaptive N (Decision 6): --n-samples defaults to
100, capped at the real eligible pool size.

No questionnaire, no clinical notes (Decision 4) -- the honest default,
matching what happens whenever a real doctor skips the questionnaire.

Ground truth: findings_clean/impression_clean ONLY (Decision 2) --
confirmed against the real master_metadata.csv schema in Step 2; no
ground truth exists anywhere for the other 5 generated fields
(examination/clinical_history/technique/recommendation/disclaimer).

Tier 1 metrics only here (BLEU/ROUGE-L/METEOR). Tier 2 (BERTScore) is a
deliberately separate, isolated-venv script (score_bertscore.py) reading
this script's saved per-case generated text -- see that script's own
docstring and ml/evaluation/requirements-bertscore.txt for why (a real,
disclosed torch CVE restriction on the standard biomedical BERT
checkpoints, confirmed in Step 3, that would otherwise force a
production-affecting torch upgrade).

Failures recorded, not skipped (Decision 9): status=generation_failed +
a real reason string, never an omitted row -- the summary must report
"N completed, M failed" explicitly.

Per-case generated text saved alongside scores (Decision 10) -- the full
7-field formatted report, not just findings/impression, so "why did BLEU
drop on case X" is answerable without rerunning the whole experiment.

Real generation parameters recorded per Decision 5 -- see this project's
development_log.md "Retroactive Finding" entry: only model and
temperature are ever actually configured by this backend; top_p/
repeat_penalty/seed/max_tokens have never been set anywhere in this
codebase and are recorded here as exactly that, not guessed at.

Output location: `ml/outputs/evaluation/generation/`, matching the REAL
existing Phase 0 convention -- gate_decision_table.csv genuinely lives
at `ml/outputs/evaluation/`, not `ml/evaluation/` as phase20_generation_
evaluation_architecture.md's Decision 11 text says; confirmed directly
against the real file location and phase0_config.yaml's own
`paths.out_dir` before writing this, not assumed from the frozen doc's
prose.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests
import sacrebleu
from nltk.tokenize import word_tokenize
from nltk.translate.meteor_score import meteor_score
from rouge_score import rouge_scorer

REPORT_FIELDS = (
    "examination", "clinical_history", "technique", "findings",
    "impression", "recommendation", "disclaimer",
)
GROUND_TRUTH_FIELDS = ("findings", "impression")  # Decision 2 -- the only two with real ground truth


@dataclass
class CaseResult:
    study_uid: str
    status: str  # "completed" | "generation_failed"
    reason: str | None = None
    generated: dict = field(default_factory=dict)      # all 7 fields, Decision 10
    ground_truth: dict = field(default_factory=dict)   # findings/impression only
    metrics: dict = field(default_factory=dict)         # {field: {bleu, rouge_l, meteor}}


def _rouge_scorer() -> rouge_scorer.RougeScorer:
    return rouge_scorer.RougeScorer(["rougeL"], use_stemmer=True)


def compute_tier1_metrics(hypothesis: str, reference: str, scorer: rouge_scorer.RougeScorer) -> dict:
    """BLEU (sacrebleu, sentence-level), ROUGE-L (F-measure), METEOR (nltk).
    Real edge case handled, not assumed away: an empty hypothesis or
    reference is scored as 0.0 across the board rather than raising --
    sacrebleu/nltk both misbehave on empty strings, and a generation that
    produced empty text for a field IS a real, reportable 0, not a crash."""
    if not hypothesis.strip() or not reference.strip():
        return {"bleu": 0.0, "rouge_l": 0.0, "meteor": 0.0}

    bleu = sacrebleu.sentence_bleu(hypothesis, [reference]).score
    rouge_l = scorer.score(reference, hypothesis)["rougeL"].fmeasure
    meteor = meteor_score([word_tokenize(reference)], word_tokenize(hypothesis))
    return {"bleu": float(bleu), "rouge_l": float(rouge_l), "meteor": float(meteor)}


def build_eligible_pool(data_root: Path) -> pd.DataFrame:
    """Real, verified-untouched test pool -- Step 1's purity gate plus
    Step 2's eligibility filter, re-derived here directly rather than
    hardcoding the 477 figure, so a future re-run against updated data
    recomputes this instead of silently trusting a stale number."""
    splits = pd.read_csv(data_root / "ml/datasets/splits/splits.csv")
    splits["uid"] = splits["uid"].astype(str)
    test_uids = set(splits.loc[splits["split"] == "test", "uid"])

    meta = pd.read_csv(data_root / "ml/datasets/metadata/master_metadata.csv")
    meta["study_uid"] = meta["study_uid"].astype(str)
    test_meta = meta[meta["study_uid"].isin(test_uids)].copy()

    frontal = test_meta[test_meta["has_frontal"] == True].copy()  # noqa: E712

    def real_text(series: pd.Series) -> pd.Series:
        return (
            series.notna()
            & (series.astype(str).str.strip() != "")
            & (series.astype(str).str.strip().str.lower() != "nan")
        )

    eligible = frontal[real_text(frontal["findings_clean"]) & real_text(frontal["impression_clean"])]
    return eligible.reset_index(drop=True)


def register_and_login(api_url: str) -> requests.Session:
    """A fresh, real doctor account per evaluation run -- avoids any
    dependency on a specific pre-existing account existing in dev.db."""
    session = requests.Session()
    email = f"phase20-eval-{int(time.time())}@example.com"
    response = session.post(
        f"{api_url}/auth/register",
        json={"email": email, "password": "phase20-eval-password", "full_name": "Phase 20 Evaluation"},
        timeout=30,
    )
    response.raise_for_status()
    return session


def run_one_case(session: requests.Session, api_url: str, row: pd.Series, data_root: Path) -> CaseResult:
    study_uid = str(row["study_uid"])
    ground_truth = {
        "findings": str(row["findings_clean"]),
        "impression": str(row["impression_clean"]),
    }

    raw_path = data_root / str(row["raw_image_path"]).replace("\\", "/")
    if not raw_path.is_file():
        return CaseResult(
            study_uid=study_uid, status="generation_failed",
            reason=f"raw image file not found: {raw_path}", ground_truth=ground_truth,
        )

    try:
        with open(raw_path, "rb") as fh:
            retrieve_response = session.post(
                f"{api_url}/retrieve",
                files={"file": (raw_path.name, fh, "image/png")},
                data={"top_k": "5", "min_similarity": "0.0"},
                timeout=120,
            )
        if retrieve_response.status_code != 200:
            return CaseResult(
                study_uid=study_uid, status="generation_failed",
                reason=f"POST /retrieve returned {retrieve_response.status_code}: {retrieve_response.text[:500]}",
                ground_truth=ground_truth,
            )
        session_id = retrieve_response.json()["session_id"]

        generate_response = session.post(
            f"{api_url}/generate-report",
            json={
                "session_id": session_id,
                "language": "en",
                "questionnaire_answers": None,  # Decision 4 -- no questionnaire
                "clinical_notes": "",           # Decision 4 -- honest default
            },
            timeout=180,
        )
        if generate_response.status_code != 200:
            return CaseResult(
                study_uid=study_uid, status="generation_failed",
                reason=f"POST /generate-report returned {generate_response.status_code}: {generate_response.text[:500]}",
                ground_truth=ground_truth,
            )
    except requests.RequestException as exc:
        return CaseResult(
            study_uid=study_uid, status="generation_failed",
            reason=f"transport error: {exc}", ground_truth=ground_truth,
        )

    content = generate_response.json()["formatted_report"]["content"]
    generated = {f: content[f] for f in REPORT_FIELDS}

    scorer = _rouge_scorer()
    metrics = {
        field_name: compute_tier1_metrics(generated[field_name], ground_truth[field_name], scorer)
        for field_name in GROUND_TRUTH_FIELDS
    }

    return CaseResult(
        study_uid=study_uid, status="completed",
        generated=generated, ground_truth=ground_truth, metrics=metrics,
    )


def _git_commit_hash(path: Path) -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=path, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except Exception:
        return "unknown"


def get_real_generation_settings(api_url: str) -> dict:
    """Decision 5 -- report exactly what's real, don't guess. Only
    model/temperature are ever configured by this backend (confirmed in
    Step 4); everything else is Ollama's own silent default."""
    ollama_base_url = "http://localhost:11434"  # real default, matches backend/app/core/config.py
    try:
        version_response = requests.get(f"{ollama_base_url}/api/version", timeout=5)
        ollama_version = version_response.json().get("version", "unknown")
    except requests.RequestException:
        ollama_version = "unreachable"

    return {
        "model": "llama3:8b",       # settings.OLLAMA_MODEL, confirmed Step 4
        "temperature": 0.0,          # settings.LLM_TEMPERATURE, confirmed Step 4
        "top_p": "not set by this system -- Ollama default applied",
        "repeat_penalty": "not set by this system -- Ollama default applied",
        "seed": "not set by this system -- Ollama default applied",
        "max_tokens": "not set by this system -- Ollama default applied",
        "ollama_version": ollama_version,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-root", default=".")
    ap.add_argument("--api-url", default="http://localhost:8000")
    ap.add_argument("--n-samples", type=int, default=100)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument(
        "--append", action="store_true",
        help="Extend an existing per_case_results.csv rather than overwrite it: "
             "excludes study_uids already present, samples --n-samples from the "
             "REMAINING eligible pool (same seed-tracked scheme), and appends "
             "new rows instead of replacing the file. Not a fresh restart.",
    )
    args = ap.parse_args()

    data_root = Path(args.data_root)
    out_dir = data_root / "ml/outputs/evaluation/generation"
    out_dir.mkdir(parents=True, exist_ok=True)
    text_dir = out_dir / "generated_text"
    text_dir.mkdir(parents=True, exist_ok=True)
    results_path = out_dir / "per_case_results.csv"

    eligible = build_eligible_pool(data_root)

    existing_df = None
    if args.append and results_path.is_file():
        existing_df = pd.read_csv(results_path, dtype={"study_uid": str})
        already_done = set(existing_df["study_uid"])
        eligible = eligible[~eligible["study_uid"].isin(already_done)].reset_index(drop=True)
        print(f"[run_generation_eval] append mode: {len(already_done)} cases already in {results_path.name}, "
              f"{len(eligible)} remaining eligible")

    n = min(args.n_samples, len(eligible))
    sample = eligible.sample(n=n, random_state=args.seed).reset_index(drop=True)
    print(f"[run_generation_eval] eligible pool (remaining): {len(eligible)}, sampling {n} (seed={args.seed})")

    session = register_and_login(args.api_url)
    print("[run_generation_eval] real doctor account registered for this run")

    rows = []
    completed = 0
    failed = 0
    start = time.perf_counter()
    for i, row in sample.iterrows():
        result = run_one_case(session, args.api_url, row, data_root)
        if result.status == "completed":
            completed += 1
            (text_dir / f"{result.study_uid}.json").write_text(
                json.dumps({"generated": result.generated, "ground_truth": result.ground_truth}, indent=2)
            )
        else:
            failed += 1
        rows.append({
            "study_uid": result.study_uid,
            "status": result.status,
            "reason": result.reason,
            **{
                f"{f}_{m}": result.metrics.get(f, {}).get(m)
                for f in GROUND_TRUTH_FIELDS for m in ("bleu", "rouge_l", "meteor")
            },
        })
        print(f"[run_generation_eval] ({i + 1}/{n}) study_uid={result.study_uid} status={result.status}")

    elapsed = time.perf_counter() - start
    new_results_df = pd.DataFrame(rows)

    if existing_df is not None:
        combined_df = pd.concat([existing_df, new_results_df], ignore_index=True)
    else:
        combined_df = new_results_df
    combined_df.to_csv(results_path, index=False)

    total_completed = int((combined_df["status"] == "completed").sum())
    total_failed = int((combined_df["status"] == "generation_failed").sum())

    print(f"[run_generation_eval] this run: {completed} completed, {failed} failed, {elapsed:.1f}s total")
    if existing_df is not None:
        print(f"[run_generation_eval] combined total: {total_completed} completed, {total_failed} failed, "
              f"{len(combined_df)} rows in {results_path.name}")

    config = {
        "phase": 20,
        "evaluation_date": datetime.now(timezone.utc).isoformat(),
        "sample_size": len(combined_df),
        "sample_source": f"{len(eligible) + (len(existing_df) if existing_df is not None else 0)} real eligible test-split cases (frontal + real findings + real impression)",
        "sample_seed": args.seed,
        "completed": total_completed,
        "failed": total_failed,
        "generation_settings": get_real_generation_settings(args.api_url),
        "ground_truth_fields": list(GROUND_TRUTH_FIELDS),
        "metrics_tier1": ["bleu", "rouge_l", "meteor"],
        "git_commit_ml": _git_commit_hash(data_root),
        "git_commit_backend": _git_commit_hash(data_root / "backend"),
    }
    (out_dir / "evaluation_config.json").write_text(json.dumps(config, indent=2))
    print(f"[run_generation_eval] wrote {out_dir / 'evaluation_config.json'}")


if __name__ == "__main__":
    main()
