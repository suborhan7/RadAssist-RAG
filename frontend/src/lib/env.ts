/**
 * lib/env.ts
 * ====================================================================
 * Environment configuration -- infra, not workflow (frozen Phase 12
 * Decision 6 deliberately keeps this separate from the clinical workflow
 * diagram/components). NEXT_PUBLIC_API_URL must be prefixed
 * NEXT_PUBLIC_ to be readable in the browser (Next.js convention -- any
 * env var without that prefix is server-only and would be undefined in
 * client components).
 *
 * Default is "localhost", not "127.0.0.1" (Phase 13 fix, found via a
 * real end-to-end browser test): this app is served from
 * http://localhost:3000, and the Phase 13a auth cookie is SameSite=Lax
 * -- browsers treat "localhost" and "127.0.0.1" as different sites for
 * cookie purposes even though both resolve to the same backend, so a
 * "127.0.0.1" API origin silently never received the cookie back.
 */

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
