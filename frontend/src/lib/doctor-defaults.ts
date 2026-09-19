/**
 * Retrieval defaults, in exactly one place.
 *
 * This module exists because of a real bug: the upload flow passed a literal
 * `topK: 5` to the API client, and the API client independently defaulted to
 * `?? 5`, and the screen header independently rendered the literal string
 * "K=5". Three unrelated 5s meant a doctor who set k=3 in Settings saw no
 * change anywhere and no error -- nothing was wired to the preference, and
 * nothing could tell you so. A single exported constant makes the fallback
 * greppable and makes a call site that hardcodes a number obvious on review.
 *
 * Plain module, no "use client": both the fetch layer (api-client.ts) and the
 * client-side preferences provider (doctor.tsx) import it.
 */
export const DEFAULT_TOP_K = 5;

/**
 * Bounds for a doctor-supplied k. The retrieval collection is the IU/Indiana
 * train split and the evidence panel is laid out for a handful of cases, not
 * an arbitrary page of them; a k outside this range is a data-entry mistake,
 * not a preference. Enforced on the server too (PATCH /auth/me) -- this copy
 * is for the input control and the client-side fallback, never the only check.
 */
export const MIN_TOP_K = 1;
export const MAX_TOP_K = 10;

/**
 * Resolve a stored preference to a usable k.
 *
 * Unset or non-numeric falls back to the default. An out-of-range number is
 * CLAMPED rather than discarded: the control used to accept up to 20, so a
 * doctor may already have 15 saved, and silently substituting 5 would mean the
 * screen says 15 while retrieval uses 5 -- reintroducing exactly the
 * label-disagrees-with-behaviour bug this module exists to prevent. Clamping to
 * 10 keeps the stored intent as close as the system allows, and Settings reads
 * through this same function so the field shows the number actually in use.
 */
export function resolveTopK(preference: number | null | undefined): number {
  if (typeof preference !== "number" || !Number.isInteger(preference)) return DEFAULT_TOP_K;
  return Math.min(Math.max(preference, MIN_TOP_K), MAX_TOP_K);
}
