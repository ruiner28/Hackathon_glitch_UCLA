import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

const SESSION_COOKIE = "vc_session";

/**
 * Protect app routes: unauthenticated users go to /login?next=...
 * Set NEXT_PUBLIC_REQUIRE_AUTH=false in .env.local to disable (local dev without OAuth).
 */
export function middleware(request: NextRequest) {
  if (process.env.NEXT_PUBLIC_REQUIRE_AUTH === "false") {
    return NextResponse.next();
  }

  if (request.cookies.has(SESSION_COOKIE)) {
    return NextResponse.next();
  }

  const login = new URL("/login", request.url);
  const returnTo =
    request.nextUrl.pathname +
    (request.nextUrl.search || "");
  login.searchParams.set("next", returnTo || "/");
  return NextResponse.redirect(login);
}

export const config = {
  matcher: ["/lesson/:path*", "/new", "/processing/:path*"],
};
