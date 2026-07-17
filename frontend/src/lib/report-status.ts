import type { ReportStatus as ChipReportStatus } from "@/components/ui/chip";

/**
 * Backend's real ReportStatus enum (app/domain/entities.py) has only ever
 * had one value, "ai_draft" (confirmed during Phase 13a: no finalize/edit/
 * regenerate workflow exists yet to produce "review"/"edited"/"final").
 * StatusChip's keys follow design_specification.md §10.1's full intended
 * status machine ("draft"/"review"/"edited"/"final") -- this maps the
 * real backend value now and passes through the not-yet-reachable values
 * defensively, rather than assuming only "ai_draft" will ever arrive.
 */
export function toChipReportStatus(backendStatus: string): ChipReportStatus {
  switch (backendStatus) {
    case "ai_draft":
      return "draft";
    case "review":
    case "edited":
    case "final":
      return backendStatus;
    default:
      return "draft";
  }
}
