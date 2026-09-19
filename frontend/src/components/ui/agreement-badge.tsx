"use client";

import { useT } from "@/lib/i18n";
import { cn } from "@/lib/cn";

/**
 * Evidence agreement. Replaces the "Confidence" surface.
 *
 * The measure is a rule over cosine similarity. Calling it confidence implies a
 * calibrated probability of diagnostic correctness the system does not have;
 * dropping it entirely loses the scan signal a radiologist needs. Naming the
 * measure after what it measures keeps both, and turns the caveat from an
 * apology into a definition.
 *
 * Never render a bare percentage. The factors are the point.
 *
 * Two-accent mapping: strong agreement reads cyan (confirmed), weak reads amber
 * (attention), and the middle "mixed" is neither, so it sits neutral grey. The
 * WORD label and the factor rows carry the distinction — colour is never the
 * only signal.
 */
export type Agreement = "strong" | "mixed" | "weak";

export interface AgreementFactors {
  agreeing: number;
  k: number;
  topSimilarity: number;
  meanSimilarity: number;
  /** null when the report endpoint doesn't report whether clinical
   * history was supplied at generation time -- render "Not recorded"
   * rather than guessing a boolean the caller has no ground truth for. */
  clinicalHistory: boolean | null;
  labelSpread: number;
}

const TONE: Record<Agreement, string> = {
  strong: "text-cyan",
  mixed: "text-text-tertiary",
  weak: "text-amber",
};
const FILL: Record<Agreement, string> = {
  strong: "bg-cyan",
  mixed: "bg-border-strong",
  weak: "bg-amber",
};
const WORD_KEY: Record<Agreement, string> = {
  strong: "agreement.strong",
  mixed: "agreement.mixed",
  weak: "agreement.weak",
};

export function AgreementBadge({ level, factors }: { level: Agreement; factors: AgreementFactors }) {
  const { t } = useT();
  const pct = Math.round((factors.agreeing / factors.k) * 100);
  return (
    <div>
      <div className="flex items-baseline justify-between">
        <div className="font-mono text-eyebrow uppercase text-text-tertiary">{t("agreement.title")}</div>
        <div className={cn("text-panel", TONE[level])}>{t(WORD_KEY[level])}</div>
      </div>

      <div className="my-10 h-4 overflow-hidden rounded-full bg-bg-raised">
        <div className={cn("h-full rounded-full", FILL[level])} style={{ width: `${pct}%` }} />
      </div>

      <p className="text-sm text-text-secondary">
        {t("agreement.agreeLine", { agreeing: factors.agreeing, k: factors.k })}
      </p>

      <dl className="mt-12 border-t border-hairline pt-10">
        <Row label={t("agreement.top1")} value={`${factors.topSimilarity.toFixed(1)}%`} />
        <Row label={t("agreement.meanSim", { k: factors.k })} value={`${factors.meanSimilarity.toFixed(1)}%`} />
        <Row
          label={t("agreement.clinHistory")}
          value={factors.clinicalHistory === null ? t("agreement.notRecorded") : factors.clinicalHistory ? t("agreement.yes") : t("agreement.no")}
          tone={factors.clinicalHistory ? "text-cyan" : "text-text-tertiary"}
        />
        <Row label={t("agreement.labelSpread")} value={t("agreement.labelsCount", { count: factors.labelSpread })} />
      </dl>

      {/* Definition, not disclaimer. */}
      <p className="mt-12 rounded-panel bg-bg-raised p-12 text-sm text-text-secondary">
        {t("agreement.defPre")}{" "}
        <strong className="text-text-primary">{t("agreement.defBold")}</strong>
      </p>
    </div>
  );
}

function Row({ label, value, tone }: { label: string; value: string; tone?: string }) {
  return (
    <div className="flex items-center gap-8 border-b border-hairline py-8 last:border-0">
      <dt className="text-sm text-text-secondary">{label}</dt>
      <dd className={cn("ml-auto font-mono text-mono-meta", tone ?? "text-text-primary")}>{value}</dd>
    </div>
  );
}
