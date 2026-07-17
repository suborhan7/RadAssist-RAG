import { cn } from "@/lib/cn";

/**
 * §10.3. Replaces the "Confidence" surface.
 *
 * The measure is a rule over cosine similarity. Calling it confidence implies a
 * calibrated probability of diagnostic correctness the system does not have;
 * dropping it entirely loses the scan signal a radiologist needs. Naming the
 * measure after what it measures keeps both, and turns the caveat from an
 * apology into a definition.
 *
 * Never render a bare percentage. The factors are the point.
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
  strong: "text-stable",
  mixed: "text-caution-ink",
  weak: "text-critical",
};
const FILL: Record<Agreement, string> = {
  strong: "bg-stable",
  mixed: "bg-caution",
  weak: "bg-critical",
};
const WORD: Record<Agreement, string> = { strong: "Strong", mixed: "Mixed", weak: "Weak" };

export function AgreementBadge({ level, factors }: { level: Agreement; factors: AgreementFactors }) {
  const pct = Math.round((factors.agreeing / factors.k) * 100);
  return (
    <div>
      <div className="flex items-baseline justify-between">
        <div className="text-eyebrow uppercase text-ink-3">Evidence agreement</div>
        <div className={cn("text-h2", TONE[level])}>{WORD[level]}</div>
      </div>

      <div className="my-2.5 h-1 overflow-hidden rounded-full bg-sunken">
        <div className={cn("h-full rounded-full", FILL[level])} style={{ width: `${pct}%` }} />
      </div>

      <p className="text-sm leading-5 text-ink-2">
        {factors.agreeing} of {factors.k} retrieved cases agree on the primary finding.
      </p>

      <dl className="mt-3 border-t border-hairline pt-2.5">
        <Row label="Top-1 similarity" value={`${factors.topSimilarity.toFixed(1)}%`} />
        <Row label={`Mean similarity (K=${factors.k})`} value={`${factors.meanSimilarity.toFixed(1)}%`} />
        <Row
          label="Clinical history provided"
          value={factors.clinicalHistory === null ? "Not recorded" : factors.clinicalHistory ? "Yes" : "No"}
          tone={factors.clinicalHistory ? "text-stable" : "text-ink-3"}
        />
        <Row label="Label spread" value={`${factors.labelSpread} labels`} />
      </dl>

      {/* Definition, not disclaimer. §10.3 */}
      <p className="mt-3 rounded-card bg-sunken p-tight text-sm leading-[18px] text-ink-2">
        Measures agreement among retrieved cases.{" "}
        <strong className="text-ink">Not a probability that the report is correct.</strong>
      </p>
    </div>
  );
}

function Row({ label, value, tone }: { label: string; value: string; tone?: string }) {
  return (
    <div className="flex items-center gap-2 border-b border-hairline py-2 last:border-0">
      <dt className="text-sm text-ink-2">{label}</dt>
      <dd className={cn("ml-auto font-mono text-data-sm", tone ?? "text-ink")}>{value}</dd>
    </div>
  );
}
