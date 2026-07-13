/**
 * lib/env.ts
 * ====================================================================
 * Environment configuration -- infra, not workflow (frozen Phase 12
 * Decision 6 deliberately keeps this separate from the clinical workflow
 * diagram/components). NEXT_PUBLIC_API_URL must be prefixed
 * NEXT_PUBLIC_ to be readable in the browser (Next.js convention -- any
 * env var without that prefix is server-only and would be undefined in
 * client components).
 */

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";
