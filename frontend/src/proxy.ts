import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

/**
 * Real, confirmed gap this fixes: nothing previously redirected an
 * unauthenticated visitor away from any protected page -- every route
 * rendered unconditionally and only a write action deep in the flow
 * would eventually 401 (e.g. filling out the entire "Register New
 * Patient" form before ever being told to sign in). Checks only the
 * auth cookie's PRESENCE, not its validity -- decoding/verifying the
 * JWT here would duplicate get_current_doctor()'s job
 * (backend/app/api/dependencies.py) and risk the two checks silently
 * drifting apart. A cookie that's present but expired/invalid is a
 * separate case, handled by api-client.ts's global 401 redirect.
 */
const AUTH_COOKIE_NAME = "radassist_token"; // must match backend/app/api/dependencies.py's AUTH_COOKIE_NAME exactly

// "/" is the public Landing page (design_specification.md §8.1, §16.1's
// reopening) -- the authenticated home lives at /dashboard instead, so
// it stays behind the gate like every other real page.
const PUBLIC_PATHS = new Set(["/", "/login", "/register"]);

export function proxy(request: NextRequest) {
  const { pathname, search } = request.nextUrl;

  if (PUBLIC_PATHS.has(pathname)) {
    return NextResponse.next();
  }

  if (!request.cookies.has(AUTH_COOKIE_NAME)) {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("redirect", pathname + search);
    return NextResponse.redirect(loginUrl);
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
