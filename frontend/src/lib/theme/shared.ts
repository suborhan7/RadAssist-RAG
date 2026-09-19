/**
 * Server-safe theme constants and types, split out for the same reason
 * i18n/shared.ts is: a plain value exported from a "use client" module
 * resolves to `undefined` when a Server Component imports it, and the root
 * layout is a Server Component that needs the real cookie name to read the
 * persisted theme before the first paint.
 */
export type Theme = "dark" | "light";

export const THEME_COOKIE = "rr_theme";

/** Dark is the design's native mode; light is the alternative. */
export const DEFAULT_THEME: Theme = "dark";
