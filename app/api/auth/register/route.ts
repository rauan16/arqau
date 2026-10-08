import { NextRequest, NextResponse } from "next/server";

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

function validateOrigin(request: NextRequest): boolean {
  const origin = request.headers.get("origin");
  const host = request.headers.get("host");
  if (!host) return false;
  if (!origin) return true;
  try {
    const originUrl = new URL(origin);
    return originUrl.host === host;
  } catch {
    return false;
  }
}

export async function POST(request: NextRequest) {
  if (!validateOrigin(request)) {
    return NextResponse.json({ error: "Invalid origin" }, { status: 403 });
  }

  let body: { email: string; password: string; name?: string };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid request body" }, { status: 400 });
  }

  const { email, password, name } = body;
  if (!email || !password) {
    return NextResponse.json({ error: "Email and password required" }, { status: 400 });
  }

  try {
    const response = await fetch(`${BACKEND_URL}/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password, name }),
    });

    const data = await response.json().catch(() => ({}));

    if (!response.ok) {
      const detail = data?.detail || data?.message || "Registration failed";
      return NextResponse.json({ error: detail }, { status: response.status });
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