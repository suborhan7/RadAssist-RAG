/**
 * Routes that render their own chrome and sit outside the rail + main frame:
 * Landing, Sign in, Register. Extracted from app-shell.tsx so DoctorProvider
 * can consult the same set without importing the shell (which imports the
 * rail, which consumes the provider -- a cycle).
 */
export const CHROMELESS_ROUTES = new Set(["/", "/login", "/register"]);
