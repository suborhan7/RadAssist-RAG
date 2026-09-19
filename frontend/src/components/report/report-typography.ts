/**
 * One typography rule for report body text, shared by every surface that renders
 * a report: the workspace sections (EditableReportSection), the finalize preview
 * and the read-only document view (ReportDocumentView).
 *
 * It exists because those surfaces had drifted. The report body was set in
 * `text-text-secondary` -- a mid-grey used elsewhere for captions and metadata --
 * so a whole clinical document was rendered in the colour reserved for labels,
 * and read as unreadable. Worse, EditableReportSection used `text-text-primary`
 * for the SAME sentence while it was being edited and `text-text-secondary` the
 * moment it was committed, so text visibly dimmed once it became real.
 *
 * The second problem was flatness: all seven fields shared one size and colour,
 * so the impression -- the conclusion a radiologist looks for first -- was set
 * identically to the disclaimer, which is fixed boilerplate. Hierarchy now
 * follows what the field is FOR:
 *
 *   impression   the conclusion            19px/500, primary   (the `impression-report`
 *                                                              token, defined for exactly
 *                                                              this and never wired up)
 *   disclaimer   fixed legal boilerplate   14px, secondary     (quiet on purpose)
 *   everything   clinical prose            16px/30, primary
 *
 * Absent values are muted rather than set as body text, so "Not provided" does
 * not read as content the report actually contains.
 */
export type ReportFieldKey =
  | "examination"
  | "clinical_history"
  | "technique"
  | "findings"
  | "impression"
  | "recommendation"
  | "disclaimer";

const BODY_BY_FIELD: Partial<Record<ReportFieldKey, string>> = {
  impression: "text-impression-report text-text-primary",
  disclaimer: "text-sm leading-relaxed text-text-secondary",
};

const DEFAULT_BODY = "text-findings text-text-primary";

/** Class for a field's value. `present=false` mutes it (an absent field). */
export function reportBodyClass(field: ReportFieldKey | undefined, present: boolean): string {
  if (!present) return "text-findings text-text-muted";
  return (field && BODY_BY_FIELD[field]) ?? DEFAULT_BODY;
}

/**
 * Section heading, as a boxed and filled label rather than a bare line of small
 * caps. Three things changed together and they only work together: the label is
 * 12.5px instead of the 10.5px eyebrow floor, it sits in a bordered chip, and
 * the chip carries a fill. On a seven-section document the unboxed version gave
 * no anchor for the eye to jump between sections -- the labels were smaller and
 * quieter than the text they introduced, which is backwards for something whose
 * whole job is to say where you are.
 *
 * IMPRESSION is the one section that gets the cyan treatment. It is the
 * conclusion, and this app already uses cyan for the thing that matters; making
 * all seven cyan would mark nothing.
 */
export function reportLabelClass(field?: ReportFieldKey): string {
  const base =
    "inline-flex items-center rounded-chip border px-10 py-5 font-mono text-section-label uppercase";
  return field === "impression"
    ? `${base} border-cyan-line bg-cyan-wash text-cyan`
    : `${base} border-strong bg-bg-hover text-text-secondary`;
}
