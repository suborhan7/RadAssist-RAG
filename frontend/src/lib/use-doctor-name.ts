"use client";

import { useEffect, useState } from "react";
import { getDoctor } from "@/lib/api-client";

/**
 * Shared resolver for GET /doctors/{doctor_id} (Phase 15), backing both
 * OwnerChip and any page-level copy that needs to name a report's owner
 * directly (e.g. the read-only banner's "This report belongs to Dr. X."
 * sentence). Module-level cache, not per-hook-instance state -- the same
 * other-doctor commonly appears in several places on one page render.
 *
 * A cache hit is read directly during render (`nameCache.get(doctorId)`),
 * never via setState -- only the genuinely asynchronous case (a real
 * network fetch still in flight) uses state, and only sets it from
 * inside the fetch's own .then()/.catch() callbacks, never synchronously
 * in the effect body. An earlier version called setState synchronously
 * at the top of the effect for both the null-doctorId and cache-hit
 * cases; a real ESLint rule (react-hooks/set-state-in-effect) caught
 * both, since synchronous setState inside an effect can cascade renders
 * and neither case actually needed it.
 */
const nameCache = new Map<string, string>();

export function useDoctorName(doctorId: string | null): string | null {
  const [fetchedName, setFetchedName] = useState<string | null>(null);

  useEffect(() => {
    if (!doctorId || nameCache.has(doctorId)) return;
    let cancelled = false;
    getDoctor(doctorId)
      .then((doctor) => {
        if (cancelled) return;
        nameCache.set(doctorId, doctor.full_name);
        setFetchedName(doctor.full_name);
      })
      .catch(() => {
        if (!cancelled) setFetchedName("Another doctor");
      });
    return () => {
      cancelled = true;
    };
  }, [doctorId]);

  if (!doctorId) return null;
  return nameCache.get(doctorId) ?? fetchedName;
}
