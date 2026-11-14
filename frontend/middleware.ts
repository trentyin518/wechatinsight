import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

const PUBLIC_PREFIXES = ["/login", "/register", "/onboarding"];

export function middleware(request: NextRequest) {
  if (process.env.NEXT_PUBLIC_AUTH_ENFORCED !== "true") {
    return NextResponse.next();
  }
  const { pathname } = request.nextUrl;
  // The marketing homepage is public; actions on it (search, accounts, …) stay
  // protected and will bounce anonymous users to /login via their own routes.
  const isPublic =
    pathname === "/" ||
    PUBLIC_PREFIXES.some((prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`));
  if (isPublic) return NextResponse.next();

  const cookieName = process.env.NEXT_PUBLIC_SESSION_COOKIE_NAME || "wi_session";
  const token = request.cookies.get(cookieName)?.value;
  if (!token) {
    const url = request.nextUrl.clone();
    url.pathname = "/login";
    url.search = "";
    return NextResponse.redirect(url);
  }
  return NextResponse.next();
}

export const config = {
  // Skip API proxy, Next internals and any file with an extension.
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico|robots.txt|.*\\..*).*)"],
};
