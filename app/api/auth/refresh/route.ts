import { NextRequest, NextResponse } from "next/server";
import { validateCsrfOrigin, createCsrfErrorResponse } from "@/lib/csrf";

const BACKEND_URL = process.env.API_URL || process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const COOKIE_NAME = "arqau_refresh";
const COOKIE_PATH = "/api/auth";

function getCookieOptions(isProduction: boolean) {
  return {
    httpOnly: true,
    secure: isProduction,
    sameSite: "lax" as const,
    path: COOKIE_PATH,
    maxAge: 60 * 60 * 24 * 14,
  };
}

export async function POST(request: NextRequest) {
  const csrf = validateCsrfOrigin(request);
  if (!csrf.valid) {
    return createCsrfErrorResponse(csrf.error || "Invalid origin");
  }

  const refreshToken = request.cookies.get(COOKIE_NAME)?.value;
  if (!refreshToken) {
    return NextResponse.json({ error: "Refresh token missing" }, { status: 401 });
  }

  try {
    const response = await fetch(`${BACKEND_URL}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });

    const data = await response.json().catch(() => ({}));

    if (!response.ok) {
      const detail = data?.detail || data?.message || "Token refresh failed";
      const res = NextResponse.json({ error: detail }, { status: response.status });
      if (response.status === 401) {
        res.cookies.delete({ name: COOKIE_NAME, path: COOKIE_PATH });
      }
      res.headers.set("Cache-Control", "no-store, private");
      return res;
    }

    const { access_token, refresh_token, ...rest } = data;
    const isProduction = process.env.NODE_ENV === "production";

    const res = NextResponse.json({ access_token, ...rest }, { status: 200 });
    if (refresh_token) {
      res.cookies.set(COOKIE_NAME, refresh_token, getCookieOptions(isProduction));
    }
    res.headers.set("Cache-Control", "no-store, private");
    return res;
  } catch {
    return NextResponse.json({ error: "Authentication service unavailable" }, { status: 503 });
  }
}