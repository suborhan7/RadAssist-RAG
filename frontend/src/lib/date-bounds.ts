/**
 * Date-of-birth bounds for the native date inputs, mirroring
 * backend/app/api/schemas.py's MIN_DATE_OF_BIRTH / validate_date_of_birth().
 *
 * `<input type="date">` without a min/max accepts a year of any length --
 * Chrome allows up to 275760 -- and a tester reached the backend's unhandled
 * date.fromisoformat() that way. These attributes make the browser refuse it
 * at the field, where the person can see why. They are a courtesy, not the
 * guarantee: the server validates independently, because a client-side bound
 * only constrains this client.
 */
export const MIN_DATE_OF_BIRTH = "1900-01-01";

/** Today as YYYY-MM-DD in the viewer's own timezone (a DOB is a local date). */
export function todayISO(): string {
  const now = new Date();
  const local = new Date(now.getTime() - now.getTimezoneOffset() * 60_000);
  return local.toISOString().slice(0, 10);
}
