import { describe, expect, it } from "vitest";
import { computeReportDiff } from "./report-diff";
import { EDITABLE_REPORT_FIELDS, type EditableReportField } from "@/app/reports/[reportId]/page";

function contentOf(overrides: Partial<Record<EditableReportField, string>> = {}): Record<EditableReportField, string> {
  const base: Record<EditableReportField, string> = {
    clinical_history: "Cough",
    technique: "Posteroanterior (PA) view",
    findings: "No pleural effusion.",
    impression: "Normal chest X-ray.",
    recommendation: "Clinical correlation.",
  };
  return { ...base, ...overrides };
}

describe("computeReportDiff", () => {
  it("zero edits: 0% REP, 0 of 5 sections changed, no diff markup on any section", () => {
    const draft = contentOf();
    const final = contentOf(); // identical values, new object
    const result = computeReportDiff(draft, final);

    expect(result.editPercentage).toBe(0);
    expect(result.sectionsChanged).toBe(0);
    expect(result.sections).toHaveLength(5);
    for (const section of result.sections) {
      expect(section.changed).toBe(false);
    }
    // every field's own list ordering matches EDITABLE_REPORT_FIELDS
    expect(result.sections.map((s) => s.field)).toEqual([...EDITABLE_REPORT_FIELDS]);
  });

  it("every word changed with zero vocabulary overlap: 5 of 5 sections changed, REP is 200% (not capped at 100%)", () => {
    // Every draft/final pair below shares zero exact word tokens (verified
    // directly: diffWordsWithSpace only matches WHOLE tokens, so as long
    // as no token string repeats between a field's draft and final text,
    // the diff is a full remove+add with no partial/unchanged match --
    // an earlier version of this test picked overlapping vocabulary
    // ("Posteroanterior (PA) view" -> "Lateral view", sharing "view") and
    // got a real, correctly-computed lower percentage instead, which is
    // why this test now deliberately controls for overlap.
    const draft = contentOf();
    const final = contentOf({
      clinical_history: "Fever", // 1 word, vs draft's 1 ("Cough")
      technique: "Supine AP portable", // 3 words, vs draft's 3
      findings: "Bilateral consolidation seen.", // 3 words, vs draft's 3
      impression: "Abnormal study result.", // 3 words, vs draft's 3
      recommendation: "Repeat imaging.", // 2 words, vs draft's 2
    });
    const result = computeReportDiff(draft, final);

    expect(result.sectionsChanged).toBe(5);
    // Equal word counts (12 draft, 12 final) with zero overlap: every one
    // of the 12 draft words is REMOVED and every one of the 12 final
    // words is ADDED -- REP sums both sides over the draft-only
    // denominator: (12 removed + 12 added) / 12 draft words * 100 = 200%.
    // This is a real, intentional property of the formula (Decision 3):
    // a wholesale rewrite of equal length is 200%, not 100% -- it is NOT
    // a similarity ratio capped at 100%, and asserting that here
    // documents this precisely rather than leaving it as a surprise.
    expect(result.editPercentage).toBe(200);
  });

  it("punctuation-only edit: real jsdiff tokenization removes the period as its own token, doesn't misbehave", () => {
    // Verified directly against the installed `diff` version before writing
    // this assertion: diffWordsWithSpace('No pleural effusion.', 'No pleural
    // effusion') returns an unchanged "No pleural effusion" chunk plus a
    // separately REMOVED "." chunk -- punctuation is its own token, not
    // fused onto the adjacent word.
    const draft = contentOf({ findings: "No pleural effusion." });
    const final = contentOf({ findings: "No pleural effusion" });
    const result = computeReportDiff(draft, final);

    const findingsSection = result.sections.find((s) => s.field === "findings")!;
    expect(findingsSection.changed).toBe(true);
    expect(findingsSection.diff.some((c) => c.removed && c.value === ".")).toBe(true);
    expect(findingsSection.diff.some((c) => !c.added && !c.removed && c.value === "No pleural effusion")).toBe(
      true,
    );

    // "." is one non-whitespace token removed, out of "No pleural effusion."'s
    // 3 real words ("No", "pleural", "effusion") -- REP > 0 (a real,
    // non-whitespace token changed) but small, and finite, not NaN.
    expect(result.editPercentage).toBeGreaterThan(0);
    expect(Number.isFinite(result.editPercentage)).toBe(true);
  });

  it("whitespace-only edit does not inflate REP, but still counts the section as changed", () => {
    const draft = contentOf({ findings: "No effusion. Clear lungs." });
    const final = contentOf({ findings: "No effusion.\nClear lungs." });
    const result = computeReportDiff(draft, final);

    const findingsSection = result.sections.find((s) => s.field === "findings")!;
    expect(findingsSection.changed).toBe(true); // a real change happened
    expect(result.editPercentage).toBe(0); // but it was pure whitespace
  });

  it("zero-word-denominator edge case: all 5 fields empty in the AI draft -> REP is 0%, not NaN or a throw", () => {
    const emptyContent: Record<EditableReportField, string> = {
      clinical_history: "",
      technique: "",
      findings: "",
      impression: "",
      recommendation: "",
    };
    const draft = emptyContent;
    // Every OTHER field must also stay empty in `final` -- using
    // contentOf()'s non-empty defaults here would make clinical_history/
    // technique/impression/recommendation "changed" too (empty -> real
    // text), which is a different scenario than the one this test names.
    const final: Record<EditableReportField, string> = {
      ...emptyContent,
      findings: "New finding added on a previously empty draft.",
    };

    expect(() => computeReportDiff(draft, final)).not.toThrow();
    const result = computeReportDiff(draft, final);

    expect(result.editPercentage).toBe(0);
    expect(Number.isNaN(result.editPercentage)).toBe(false);
    // the section itself is still correctly flagged as changed --
    // REP's zero-denominator rule doesn't suppress that.
    expect(result.sections.find((s) => s.field === "findings")!.changed).toBe(true);
    expect(result.sectionsChanged).toBe(1);
  });
});
