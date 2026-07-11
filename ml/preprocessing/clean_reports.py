"""
clean_reports.py
====================================================================
Phase 1 (Dataset Foundation) -- report cleaning.

Produces embedding-ready clean text from raw findings/impression:
  - collapses de-identification tokens (XXXX...) into a single placeholder
  - strips residual OCR/typo artifacts common in this corpus (double spaces,
    stray punctuation runs, "." as its own sentence)
  - builds `full_text` (findings + impression) used downstream for text
    embedding and the LLM knowledge-base chunks
  - flags studies where findings is missing (impression-only) so the
    generation-eval split can exclude them, per the frozen protocol

Reads indiana_reports.csv, joins onto the existing study_index.csv (from
build_study_index.py) so the split/label columns and clean text live in one
place -> outputs/study_index_clean.csv

Usage:
    python scripts/clean_reports.py --config config/phase0_config.yaml --data-root .
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

import pandas as pd
import yaml

DEIDENT_RE = re.compile(r"\bx{2,}\b", flags=re.IGNORECASE)
WHITESPACE_RE = re.compile(r"\s+")
STRAY_PUNCT_RE = re.compile(r"\s+([.,;:])")
LONE_PERIOD_RE = re.compile(r"(?:^|\.\s*)\.\s*(?=\.|$)")  # collapses ". ." runs


def clean_text(text: str) -> str:
    if not isinstance(text, str) or not text.strip() or text.strip().lower() == "nan":
        return ""
    t = DEIDENT_RE.sub("[REDACTED]", text)
    t = STRAY_PUNCT_RE.sub(r"\1", t)
    t = LONE_PERIOD_RE.sub(". ", t)
    t = WHITESPACE_RE.sub(" ", t).strip()
    return t


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config/phase0_config.yaml")
    ap.add_argument("--data-root", default=".")
    args = ap.parse_args()

    with open(args.config) as fh:
        cfg = yaml.safe_load(fh)
    metadata_dir = Path(cfg["paths"]["metadata_dir"])
    data_root = Path(args.data_root)

    idx = pd.read_csv(metadata_dir / "study_index.csv")
    reports = pd.read_csv(data_root / cfg["paths"]["reports_csv"])[
        ["uid", "findings", "impression"]
    ]

    reports["findings_clean"] = reports["findings"].apply(clean_text)
    reports["impression_clean"] = reports["impression"].apply(clean_text)
    reports["has_findings"] = reports["findings_clean"].str.len() > 0
    reports["full_text"] = (
        reports["findings_clean"] + " " + reports["impression_clean"]
    ).str.strip()

    merged = idx.merge(
        reports[["uid", "findings_clean", "impression_clean", "has_findings", "full_text"]],
        on="uid", how="left",
    )

    out_path = metadata_dir / "study_index_clean.csv"
    merged.to_csv(out_path, index=False)

    n_no_findings = (~merged["has_findings"]).sum()
    n_empty_full = (merged["full_text"].str.len() == 0).sum()
    print(f"[clean_reports] studies: {len(merged)}")
    print(f"[clean_reports] missing findings (impression-only): {n_no_findings} "
          f"-> excluded from generation-eval target, kept in KB")
    print(f"[clean_reports] studies with empty full_text (both missing): {n_empty_full}")
    print(f"[clean_reports] wrote {out_path}")


if __name__ == "__main__":
    main()
