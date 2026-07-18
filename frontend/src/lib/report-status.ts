import type { ReportStatus as ChipReportStatus } from "@/components/ui/chip";

/**
 * Backend's real ReportStatus enum (app/domain/entities.py) serializes as
 * "ai_draft" | "under_review" | "doctor_edited" | "final" (.value, see
 * app/api/reports.py's `status=detail.status.value`). Phase 17 makes
 * "doctor_edited" and "final" real and reachable for the first time via
 * PATCH /reports/{id} and PATCH /reports/{id}/finalize -- "under_review"
 * stays permanently defined-but-unreachable (no dwell-timer mechanism was
 * built, a deliberate rejection of an unverifiable mechanism, not an
 * oversight).
 *
 * Found and fixed here (Phase 17 Step 6): this function previously mapped
 * the literal string "edited", which the backend never actually sends --
 * a real DOCTOR_EDITED report silently fell through to the `default:
 * return "draft"` branch, rendering incorrect "AI Draft" styling on an
 * edited report.
 *
 * StatusChip's keys ("draft"/"review"/"edited"/"final") follow
 * design_specification.md §10.1's full intended status machine -- this
 * maps every real backend value to its corresponding chip key.
 */
export function toChipReportStatus(backendStatus: string): ChipReportStatus {
  switch (backendStatus) {
    case "ai_draft":
      return "draft";
    case "under_review":
      return "review";
    case "doctor_edited":
      return "edited";
    case "final":
      return "final";
    default:
      return "draft";
  }
}
