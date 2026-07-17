import type { Agreement, AgreementFactors } from "@/components/ui/agreement-badge";

interface RetrievedCaseLike {
  similarity: number;
  primary_label: string;
}

/**
 * Client-side tally over the SAME retrieved_cases already present on
 * GET /reports/{report_id} -- not a second backend call, not invented
 * data. Mirrors what LabelVotingService.vote() computes server-side
 * (Phase 4/7's frozen label-voting tally), replicated here because
 * ReportDetailResponse does not carry voted_labels (only POST /retrieve's
 * response does, per the frozen response contract) -- see the Phase 14
 * dev log entry for why this is a client-side re-derivation, not a
 * second source of truth for anything the backend itself decides.
 *
 * Strong/Mixed/Weak thresholds are a frontend-only display convenience,
 * not a backend-computed clinical classification -- design_specification.md
 * §10.2 requires a headline word, but names no numeric threshold ("Threshold
 * is configuration, never a literal" is stated about a DIFFERENT threshold,
 * the retrieval Skip-affordance in §8.10). These are picked reasonably and
 * documented here, not silently presented as a validated clinical cutoff.
 */
export function computeAgreement(cases: RetrievedCaseLike[]): {
  level: Agreement;
  factors: AgreementFactors;
  topLabel: string;
  presentLabels: { label: string; count: number; k: number }[];
} {
  const k = cases.length;
  const byLabel = new Map<string, number>();
  for (const c of cases) {
    byLabel.set(c.primary_label, (byLabel.get(c.primary_label) ?? 0) + 1);
  }
  const presentLabels = [...byLabel.entries()]
    .map(([label, count]) => ({ label, count, k }))
    .sort((a, b) => b.count - a.count);

  const topLabel = presentLabels[0]?.label ?? "";
  const agreeing = presentLabels[0]?.count ?? 0;
  const fraction = k > 0 ? agreeing / k : 0;
  const level: Agreement = fraction >= 0.6 ? "strong" : fraction >= 0.3 ? "mixed" : "weak";

  const similarities = cases.map((c) => c.similarity * 100);
  const topSimilarity = similarities.length ? Math.max(...similarities) : 0;
  const meanSimilarity = similarities.length
    ? similarities.reduce((a, b) => a + b, 0) / similarities.length
    : 0;

  return {
    level,
    topLabel,
    presentLabels,
    factors: {
      agreeing,
      k,
      topSimilarity,
      meanSimilarity,
      clinicalHistory: null,
      labelSpread: byLabel.size,
    },
  };
}
