import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { REPORT_CONTENT_FIELDS } from "./report-document-view";

/**
 * Regression test for the 7-field label-list consolidation (post-Phase-18
 * cleanup): page.tsx and compare/page.tsx each independently redeclared
 * an identical copy of this list before this refactor -- confirmed
 * byte-for-byte identical across all three before consolidating, not
 * assumed. This test locks in that exact "before" content as a snapshot
 * so an accidental future edit to the canonical list is caught, and
 * separately proves the two duplicate declarations were actually
 * removed (not left as unused dead code sitting next to the new import).
 */
describe("REPORT_CONTENT_FIELDS (canonical 7-field label list)", () => {
  it("matches the exact content verified identical across all 3 pre-consolidation copies", () => {
    expect(REPORT_CONTENT_FIELDS).toEqual([
      { key: "examination", label: "Examination" },
      { key: "clinical_history", label: "Clinical History" },
      { key: "technique", label: "Technique" },
      { key: "findings", label: "Findings" },
      { key: "impression", label: "Impression" },
      { key: "recommendation", label: "Recommendation" },
      { key: "disclaimer", label: "Disclaimer" },
    ]);
  });

  it("page.tsx and compare/page.tsx no longer redeclare their own copy", () => {
    const repoSrc = fileURLToPath(new URL("../../..", import.meta.url));

    const pageSource = readFileSync(`${repoSrc}/src/app/reports/[reportId]/page.tsx`, "utf-8");
    const compareSource = readFileSync(
      `${repoSrc}/src/app/reports/[reportId]/compare/page.tsx`,
      "utf-8",
    );

    // The old duplicate declarations both started with this exact line
    // (a `const CONTENT_FIELDS: ... = [` array literal). Its absence
    // proves the redeclaration was actually removed, not left as unused
    // dead code alongside the new import -- the import alone wouldn't
    // catch a copy silently still sitting in the file.
    const duplicateDeclarationPattern = /const CONTENT_FIELDS:\s*\{[^}]*\}\[\]\s*=\s*\[/;

    expect(pageSource).not.toMatch(duplicateDeclarationPattern);
    expect(compareSource).not.toMatch(duplicateDeclarationPattern);

    // Both must import the canonical list instead.
    expect(pageSource).toContain(
      'import { REPORT_CONTENT_FIELDS as CONTENT_FIELDS } from "@/components/report/report-document-view"',
    );
    expect(compareSource).toContain(
      'import { REPORT_CONTENT_FIELDS as CONTENT_FIELDS } from "@/components/report/report-document-view"',
    );
  });
});
