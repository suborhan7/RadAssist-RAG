"use client";

import { useT } from "@/lib/i18n";
import { cn } from "@/lib/cn";

/**
 * Retrieval support — §7.4 (S8/S9) of
 * docs/methodology/input_admission_modality_gate_architecture_v1.0_FROZEN.md.
 *
 * The SECOND evidence signal. `AgreementBadge` next to this one answers
 * "do the retrieved cases agree with each other?"; this answers "are the
 * retrieved cases near to this image?". §7.1 is emphatic that they are
 * independent and can disagree: five cases all below the support floor
 * can carry the same label, so agreement reads high while support reads
 * low, and a reader taking the agreement panel alone would come away with
 * the opposite of the truth.
 *
 * That is why this renders inside the agreement tab rather than in a
 * quiet corner of its own. The panel that could mislead is the panel that
 * has to carry the correction.
 *
 * S9: this component CALCULATES NOTHING. It receives the category the
 * backend stored with the report and renders it. The comparison of the
 * top-1 similarity against the retrieval floor happens once, in
 * ModalityGateService, and is persisted on the report row at generation
 * time (S5). Re-deriving it here from `retrieved_cases` is exactly the
 * pattern S9's Note names as a known existing defect for the agreement
 * score — where the frontend's own re-derivation can show a different
 * number than the backend computed for the same report. It is not
 * repeated here.
 *
 * The wording follows §7.2's closing Rule: the measurement shows the
 * top-1 similarity is below the configured floor. It does NOT show that
 * the archive holds no similar case. Nothing here says otherwise.
 */
export type RetrievalSupportCategory = "at_or_above_floor" | "below_floor";

export function RetrievalSupportNotice({
  category,
  topSimilarity,
  className,
}: {
  /** null for a report generated before the support signal was recorded —
   * rendered as "not recorded", never as below-floor. */
  category: RetrievalSupportCategory | null;
  topSimilarity: number | null;
  className?: string;
}) {
  const { t } = useT();

  // Amber reads as attention, matching AgreementBadge's "weak"; cyan reads
  // as confirmed. An unrecorded value is neither, so it stays neutral —
  // the same three-way tone logic the agreement surface already uses, so
  // the two panels are read with one visual vocabulary.
  const tone =
    category === "below_floor"
      ? "text-amber"
      : category === "at_or_above_floor"
        ? "text-cyan"
        : "text-text-tertiary";

  const wordKey =
    category === "below_floor"
      ? "support.below"
      : category === "at_or_above_floor"
        ? "support.atOrAbove"
        : "support.notRecorded";

  return (
    <section className={cn("rounded-panel border border-hairline p-14", className)}>
      <div className="flex items-baseline justify-between">
        <h3 className="font-mono text-eyebrow uppercase text-text-tertiary">{t("support.title")}</h3>
        <span className={cn("text-panel", tone)}>{t(wordKey)}</span>
      </div>

      <dl className="mt-12 border-t border-hairline pt-10">
        <div className="flex items-center gap-8">
          <dt className="text-sm text-text-secondary">{t("support.top1")}</dt>
          <dd className="ml-auto font-mono text-mono-meta text-text-primary">
            {topSimilarity === null ? t("support.notRecorded") : `${(topSimilarity * 100).toFixed(1)}%`}
          </dd>
        </div>
      </dl>

      <p className="mt-12 text-sm leading-relaxed text-text-secondary">
        {category === "below_floor" ? t("support.belowNote") : t("support.def")}
      </p>
    </section>
  );
}
