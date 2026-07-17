"use client";

import { OwnershipChip } from "@/components/ui/chip";
import { useDoctorName } from "@/lib/use-doctor-name";

/**
 * design_specification.md §7's OwnershipChip needs the OTHER doctor's
 * name when a session/report/comparison/explanation isn't the current
 * doctor's own -- resolved via useDoctorName (GET /doctors/{doctor_id},
 * Phase 15), cached at module scope since the same rail/timeline
 * commonly renders several chips for the same other doctor.
 *
 * Renders nothing for `ownerId === null` (a pre-Phase-13 row created
 * before doctor_id existed) -- OwnershipChip's own contract is "you" or
 * "a named doctor," and inventing a third "unowned" visual state wasn't
 * asked for and isn't backed by any real semantics worth stating.
 */
export function OwnerChip({
  ownerId,
  currentDoctorId,
}: {
  ownerId: string | null;
  currentDoctorId: string | null;
}) {
  const isMine = ownerId !== null && currentDoctorId !== null && ownerId === currentDoctorId;
  const otherName = useDoctorName(isMine ? null : ownerId);

  if (ownerId === null) return null;
  if (isMine) return <OwnershipChip doctor={null} />;
  return <OwnershipChip doctor={otherName ?? "..."} />;
}
