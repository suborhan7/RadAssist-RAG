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

  it("no consumer redeclares its own copy of the list", () => {
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

    // The workspace renders all 7 sections, so it must import the canonical
    // list rather than restate it.
    expect(pageSource).toContain(
      'import { REPORT_CONTENT_FIELDS as CONTENT_FIELDS } from "@/components/report/report-document-view"',
    );

    // Compare deliberately does NOT: the Reading Room redesign replaced its
    // side-by-side full-report dump with the two impressions (see that file's
    // docstring), so it renders no field list at all. This assertion used to
    // require the import here too and had been failing at HEAD ever since that
    // redesign landed -- the requirement went away, the test did not. What
    // still matters is the rule above: if it ever renders the list again, it
    // imports the canonical one.
    expect(compareSource).not.toMatch(duplicateDeclarationPattern);
  });
});
