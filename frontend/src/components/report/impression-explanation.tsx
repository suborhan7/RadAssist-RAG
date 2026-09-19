"use client";

import { useMemo, useState } from "react";
import { CopyButton } from "@/components/ui/copy-button";
import { computeAgreement } from "@/lib/evidence-agreement";
import { useT } from "@/lib/i18n";
import { cn } from "@/lib/cn";

/**
 * The AI reasoning card on the Explainability screen.
 *
 * Replaces a single unbroken paragraph. A radiologist scanning this needs four
 * things in descending order -- what the impression is, how well the retrieved
 * evidence agrees, which findings the report actually states, and only then the
 * model's prose -- so the card is built in exactly that order and the timing
 * sits last, as metadata.
 *
 * WHAT THIS DOES NOT DO, deliberately: it does not manufacture a list of
 * "supporting findings" out of the model's answer. The API returns one free-text
 * string for the answer and carries no structured evidence, so any ticked list
 * built from it would be asserting a finding-to-impression relationship that
 * nothing in the system computed. The findings list here is a presentation split
 * of `report.content.findings` -- the report's OWN findings section -- shown as
 * the discrete statements it is already written as, with a neutral marker rather
 * than a checkmark. A tick would claim "this supports the impression"; a dash
 * claims only "the report says this", which is all that is true.
 *
 * Everything rendered is real: the impression and findings come from the report,
 * the agreement figures from computeAgreement over the same retrieved_cases the
 * rest of the app uses, and the prose is the model's answer verbatim.
 */
export function ImpressionExplanation({
  question,
  answer,
  impression,
  findings,
  retrievedCases,
  elapsedMs,
}: {
  question: string;
  answer: string;
  impression: string;
  findings: string;
  retrievedCases: { similarity: number; primary_label: string }[];
  elapsedMs?: number;
}) {
  const { t } = useT();
  const [showReasoning, setShowReasoning] = useState(true);

  const agreement = useMemo(() => computeAgreement(retrievedCases), [retrievedCases]);
  const findingLines = useMemo(() => splitStatements(findings), [findings]);

  const AGREEMENT_TONE = { strong: "text-cyan", mixed: "text-text-secondary", weak: "text-amber" } as const;

  return (
    <article className="rounded-panel border border-hairline bg-bg-raised">
      {/* Header: the question leads, the model is named quietly, timing is metadata. */}
      <header className="flex flex-wrap items-start gap-x-14 gap-y-6 border-b border-hairline px-22 py-18">
        <div className="min-w-0 flex-1">
          <h2 className="text-panel text-text-primary">{question}</h2>
          <p className="mt-3 text-caption text-text-tertiary">{t("explain.aiExplanation")}</p>
        </div>
        {elapsedMs !== undefined && (
          <span className="whitespace-nowrap pt-4 font-mono text-mono-meta text-text-muted">
            {(elapsedMs / 1000).toFixed(1)}s
          </span>
        )}
      </header>

      <div className="flex flex-col gap-22 px-22 py-20">
        {/* 1. Impression -- the answer to "what did it conclude". */}
        <section>
          <h3 className="text-caption text-text-tertiary">{t("explain.labelImpression")}</h3>
          <p className="mt-8 border-l-2 border-cyan pl-16 text-impression-report text-text-primary">
            {impression || t("compare.none")}
          </p>
        </section>

        {/* 2. Evidence strength -- one line, because the full factor breakdown
               already lives on the workspace's Agreement tab. */}
        <section className="border-t border-hairline pt-18">
          <h3 className="text-caption text-text-tertiary">{t("explain.labelEvidence")}</h3>
          <div className="mt-8 flex flex-wrap items-baseline gap-x-12 gap-y-4">
            <span className={cn("text-panel", AGREEMENT_TONE[agreement.level])}>
              {t(`agreement.${agreement.level}`)}
            </span>
            <span className="text-sm text-text-secondary">
              {t("explain.agreeOn", {
                agreeing: agreement.factors.agreeing,
                k: agreement.factors.k,
                label: agreement.topLabel,
              })}
            </span>
          </div>
        </section>

        {/* 3. What the report itself states. Neutral markers -- see the module
               docstring for why these are not checkmarks. */}
        {findingLines.length > 0 && (
          <section className="border-t border-hairline pt-18">
            <h3 className="text-caption text-text-tertiary">{t("explain.labelFindings")}</h3>
            <ul className="mt-10 flex max-w-[62ch] flex-col gap-8">
              {findingLines.map((line, i) => (
                <li key={i} className="flex gap-10 text-sm leading-relaxed text-text-primary">
                  <span aria-hidden className="select-none pt-px font-mono text-mono-meta text-text-muted">
                    &ndash;
                  </span>
                  <span>{line}</span>
                </li>
              ))}
            </ul>
          </section>
        )}

        {/* 4. The model's prose, last and collapsible. Never hides the
               impression above it, and opens by default. */}
        <section className="border-t border-hairline pt-18">
          <div className="flex items-baseline gap-14">
            <h3 className="text-caption text-text-tertiary">{t("explain.labelReasoning")}</h3>
            <span className="flex-1" />
            <button
              type="button"
              onClick={() => setShowReasoning((v) => !v)}
              aria-expanded={showReasoning}
              className="rounded-control px-8 py-4 text-caption text-text-tertiary transition-colors duration-hover hover:bg-bg-hover hover:text-text-primary"
            >
              {showReasoning ? t("explain.hideReasoning") : t("explain.showReasoning")}
            </button>
          </div>

          {showReasoning && (
            <>
              {/* Primary text, not secondary: this is the longest run on the card and
                  readability was the reported complaint. Hierarchy below the
                  impression is already carried by size (17 vs 19), position and
                  the section label -- it does not need to be carried by dimming
                  the thing the reader is here to read. */}
              <p className="mt-10 max-w-[62ch] whitespace-pre-wrap text-answer text-text-primary">
                {answer}
              </p>
              <div className="-ml-10 mt-10 flex">
                <CopyButton text={answer} labelledBy={question} />
              </div>
            </>
          )}
        </section>
      </div>
    </article>
  );
}

/**
 * Split a findings paragraph into the discrete statements it is already written
 * as. Presentation only -- no text is added, removed or reworded.
 *
 * Splits after `.` or `;` ONLY when the next character starts a new sentence, so
 * a measurement such as "1.9 cm" and an abbreviation followed by a lowercase
 * word both stay intact. If nothing matches, the paragraph is returned whole,
 * which is still correct -- the list degrades to one item rather than mangling
 * clinical text.
 */
function splitStatements(text: string): string[] {
  const trimmed = text?.trim() ?? "";
  if (!trimmed) return [];
  return trimmed
    .split(/(?<=[.;])\s+(?=[A-Z(])/)
    .map((s) => s.trim())
    .filter(Boolean);
}
