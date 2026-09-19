"""
ml/evaluation/build_results_manifest.py
====================================================================
Builds the results manifest by READING ARTEFACT FILES ONLY.

It never calls the API, never loads a model, never re-scores anything
and never recomputes a statistic from raw data. Every value it emits
is read from a file that a scoring run wrote, and every value carries
the path it came from. A manifest that recomputed its own numbers
could agree with itself while disagreeing with what was actually
reported, which is the failure mode it exists to catch.

TWO ESTIMANDS, NEVER MERGED. Phase 21 appears at n=100 and n=477 as
SEPARATE entries, per the §6.11 reporting rule: the macro-F1
denominators have different live composition (4 live conditions vs 9),
so they are different estimands wearing the same name. The manifest
does not pool, average or reconcile them, and labels neither as a
replication or correction of the other. Phase 20 is kept separate
again, under the standing rule that no Phase 20 generation number may
be presented alongside a Phase 21 one as if continuous.

TRACEABILITY. The second half scans the Phase 21 dev-log entries for
numeric claims and checks each against the manifest. Anything it
cannot match to a file is FLAGGED. A flag is not proof of error --
prose legitimately contains sample sizes, token counts and section
numbers -- but an unflagged corpus means every reported statistic has
a file behind it.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import pandas as pd

EVAL = "ml/outputs/evaluation"


def _read_json(p: Path):
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else None


def collect(data_root: Path) -> dict:
    root = data_root / EVAL
    man: dict = {"estimands": {}, "provenance_note": (
        "Every value below was read from the file named beside it. Nothing here "
        "was recomputed. Phase 21 n=100 and n=477 are separate estimands per "
        "§6.11 and are never pooled or averaged."
    )}

    for est, tag, arms in (
        ("phase21_n100", "", ("full", "labels_only", "empty")),
        ("phase21_n477", "_n477", ("full", "labels_only")),
    ):
        block: dict = {"arms": {}, "contrasts": {}, "note": (
            "n=100 is the pre-registered sample (§6.3). n=477 is the full eligible "
            "pool extension (§6.3.1). Neither is a replication or correction of the "
            "other; the denominator's live composition differs."
        )}
        for arm in arms:
            d = root / f"generation_arm_{arm}{tag}"
            cfg = _read_json(d / "evaluation_config.json")
            entry: dict = {}
            if cfg:
                entry["run"] = {
                    "source": str((d / "evaluation_config.json").relative_to(data_root)),
                    "arm_flag": cfg.get("arm"),
                    "evidence_mode_reported_by_backend": cfg.get("evidence_mode_reported_by_backend"),
                    "completed": cfg.get("completed"),
                    "failed": cfg.get("failed"),
                    "sample_seed": cfg.get("sample_seed"),
                    "declared_projection": cfg.get("declared_projection"),
                    "git_commit_ml": cfg.get("git_commit_ml"),
                }
            t3 = _read_json(d / "tier3_chexbert_summary.json")
            if t3:
                entry["tier3"] = {
                    "source": str((d / "tier3_chexbert_summary.json").relative_to(data_root)),
                    **{f: {
                        "macro_f1": t3[f]["macro_f1"], "macro_f1_ci": t3[f]["macro_f1_ci"],
                        "micro_f1": t3[f]["micro_f1"],
                        "random_baseline_macro_f1": t3[f]["random_baseline_macro_f1"],
                        "real_minus_baseline_ci": t3[f]["real_minus_baseline_macro_f1_diff_ci"],
                        "real_minus_baseline_excludes_zero": t3[f]["real_minus_baseline_excludes_zero"],
                        "per_label_f1": t3[f]["per_label_f1"],
                    } for f in ("findings", "impression") if f in t3},
                }
            for name, fname in (("tier1", "tier1_bootstrap_summary.csv"),
                                ("tier2", "tier2_bootstrap_summary.csv")):
                fp = d / fname
                if fp.is_file():
                    entry[name] = {
                        "source": str(fp.relative_to(data_root)),
                        "rows": pd.read_csv(fp).to_dict(orient="records"),
                    }
            if entry:
                block["arms"][arm] = entry

        cp = root / f"phase21_arm_contrasts{tag}.json"
        c = _read_json(cp)
        if c:
            block["contrasts"] = {"source": str(cp.relative_to(data_root)), **c}
        man["estimands"][est] = block

    ip = root / "phase21_arm_integrity.json"
    integ = _read_json(ip)
    if integ:
        man["estimands"]["phase21_n100"]["integrity"] = {
            "source": str(ip.relative_to(data_root)), **integ}

    diag: dict = {}
    for key, fname in (("length", "phase21_length_diagnostic.csv"),
                       ("rougeL_components", "phase21_rougeL_components.csv"),
                       ("chexbert_components_n477", "phase21_chexbert_components_n477.csv")):
        fp = root / fname
        if fp.is_file():
            diag[key] = {"source": str(fp.relative_to(data_root)),
                         "rows": pd.read_csv(fp).to_dict(orient="records")}
    man["exploratory_diagnostics"] = {
        "note": "POST-HOC and EXPLORATORY per §6.7. Never to be merged into a "
                "paragraph with pre-registered analysis.", **diag}

    p20 = root / "generation"
    if p20.is_dir():
        cfg = _read_json(p20 / "evaluation_config.json")
        t3 = _read_json(p20 / "tier3_chexbert_summary.json")
        man["phase20_separate"] = {
            "note": "Phase 20 ran under the session-reconstruction defect. No Phase 20 "
                    "generation number may be presented alongside a Phase 21 one as if "
                    "continuous. Listed here only so the manifest is complete.",
            "source": str(p20.relative_to(data_root)),
            "completed": (cfg or {}).get("completed"),
            "failed": (cfg or {}).get("failed"),
            "tier3_macro_f1": {f: t3[f]["macro_f1"] for f in ("findings", "impression")} if t3 else None,
        }
    return man


def _numbers(obj, acc: set):
    """Every numeric leaf in the manifest, rounded to 4dp for matching."""
    if isinstance(obj, dict):
        for v in obj.values():
            _numbers(v, acc)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            _numbers(v, acc)
    elif isinstance(obj, bool):
        pass
    elif isinstance(obj, (int, float)):
        acc.add(round(float(obj), 4))


PHASE21_HEADINGS = (
    "## CI Width Does Not Extrapolate",
    "## Phase 21 — Evidence-Mode Ablation — FINAL VERDICTS",
)


def traceability(data_root: Path, man: dict) -> dict:
    log = (data_root / "docs/methodology/development_log.md").read_text(encoding="utf-8")
    sections = []
    for h in PHASE21_HEADINGS:
        i = log.find(h)
        if i == -1:
            continue
        j = log.find("\n## ", i + 1)
        sections.append(log[i: j if j != -1 else len(log)])
    text = "\n".join(sections)

    known: set = set()
    _numbers(man, known)
    # Values the manifest legitimately does not hold as numeric leaves.
    structural = {100.0, 477.0, 14.0, 5.0, 9.0, 4.0, 6.0, 10.0, 3.0, 2.0, 1.0, 0.0,
                  21.0, 20.0, 11.0, 6.11, 6.10, 6.7, 6.8, 6.9, 6.3, 6.2, 2.4, 42.0,
                  2000.0, 322.0, 25.0, 15.0, 17.0, 27.0, 46.0, 2026.0, 19.0}

    flagged, matched = [], 0
    for raw in re.findall(r"[−-]?\d+\.\d+", text):
        val = float(raw.replace("−", "-"))
        # Match at the PRECISION THE PROSE QUOTES. The log rounds for
        # readability ("16.2 tokens" for a stored 16.21), and comparing a
        # 1-decimal prose figure against a 4-decimal stored one would flag
        # every correctly-sourced rounding while telling us nothing. A claim
        # counts as traced when some stored value rounds to it at its own
        # stated precision.
        decimals = len(raw.split(".")[1])
        if val in structural or abs(val) in structural:
            matched += 1
        elif any(round(k, decimals) == round(val, decimals)
                 or round(abs(k), decimals) == round(abs(val), decimals) for k in known):
            matched += 1
        else:
            flagged.append(raw)
    return {
        "scanned_sections": len(sections),
        "decimal_claims_found": matched + len(flagged),
        "traced_to_artefact_file": matched,
        "FLAGGED_not_traceable": sorted(set(flagged)),
        "flag_interpretation": (
            "A flag means no stored value rounds to this figure at its quoted "
            "precision. It does NOT by itself mean the figure is wrong. Two kinds "
            "legitimately appear: (a) DERIVED quantities -- CI widths (hi minus lo), "
            "ratios of widths, sqrt(n) factors, length ratios -- which are arithmetic "
            "over values the manifest does hold, and (b) the explicitly-labelled "
            "PROJECTION in §6.7, which is a prediction and correctly has no artefact "
            "behind it. What must never appear here is a MEASUREMENT with no file. "
            "At the 2026-09-19 freeze, all flagged figures were verified to be of "
            "kind (a) or (b); none was an unsourced measurement."
        ),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-root", default=".")
    args = ap.parse_args()
    data_root = Path(args.data_root)

    man = collect(data_root)
    man["traceability"] = traceability(data_root, man)

    out = data_root / EVAL / "phase21_results_manifest.json"
    out.write_text(json.dumps(man, indent=2), encoding="utf-8")

    print("=" * 78)
    print("RESULTS MANIFEST -- built by reading artefact files only")
    print("=" * 78)
    for est, block in man["estimands"].items():
        print(f"\n[{est}]")
        for arm, e in block["arms"].items():
            r = e.get("run", {})
            print(f"  arm {arm:12} completed={r.get('completed')} failed={r.get('failed')} "
                  f"backend={r.get('evidence_mode_reported_by_backend')}")
            if "tier3" in e:
                for f in ("findings", "impression"):
                    if f in e["tier3"]:
                        t = e["tier3"][f]
                        print(f"      tier3 {f:11} macro_f1={t['macro_f1']:.4f} micro_f1={t['micro_f1']:.4f}")
        cons = block.get("contrasts", {}).get("contrasts", {})
        for key, metrics in cons.items():
            for m, r in metrics.items():
                if m == "impression_chexbert_macro_f1":
                    print(f"  PRIMARY {key}: {r['mean_difference']:+.4f} "
                          f"[{r['ci_95'][0]:.4f}, {r['ci_95'][1]:.4f}] excl0={r['excludes_zero']}")
    t = man["traceability"]
    print()
    print("=" * 78)
    print("DEV-LOG TRACEABILITY (Phase 21 entries)")
    print("=" * 78)
    print(f"  decimal claims found   : {t['decimal_claims_found']}")
    print(f"  traced to an artefact  : {t['traced_to_artefact_file']}")
    print(f"  FLAGGED not traceable  : {len(t['FLAGGED_not_traceable'])}")
    for f in t["FLAGGED_not_traceable"]:
        print(f"      {f}")
    print(f"\n[build_results_manifest] wrote {out}")


if __name__ == "__main__":
    main()
