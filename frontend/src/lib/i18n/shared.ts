/**
 * Server-safe i18n constants and types. These live OUTSIDE the "use client"
 * provider module on purpose: a plain value exported from a "use client" file
 * (index.tsx) resolves to `undefined` when a Server Component imports it (Next
 * replaces the module with a client reference). The root layout is a Server
 * Component and needs the real cookie name to read the persisted language, so
 * the constant has to come from a module with no "use client" directive.
 */
export type Lang = "en" | "bn";

export const LANG_COOKIE = "rr_lang";

/**
 * A dictionary maps an i18n key to either a static string or a function of
 * interpolation params (counts, names) returning the finished string. Params
 * are loosely typed so call sites can read `p.count` / `p.name` without casts —
 * dictionaries are hand-authored and the parity gate guards the key set.
 */
export type Dict = Record<string, string | ((p: Record<string, unknown>) => string)>;
