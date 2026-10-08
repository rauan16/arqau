import { NextRequest, NextResponse } from "next/server";

const BACKEND_URL = process.env.API_URL || process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const COOKIE_NAME = "arqau_refresh";
const COOKIE_PATH = "/api/auth";

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

  const refreshToken = request.cookies.get(COOKIE_NAME)?.value;

  if (refreshToken) {
    try {
      await fetch(`${BACKEND_URL}/auth/logout`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: refreshToken }),
      });
    } catch {
      // Ignore backend logout errors; cookie will be cleared regardless
    }
  }

  const res = NextResponse.json({ ok: true }, { status: 200 });
  res.cookies.delete({ name: COOKIE_NAME, path: COOKIE_PATH });
  res.cookies.delete({ name: COOKIE_NAME, path: "/api/auth/refresh" });
  res.headers.set("Cache-Control", "no-store, private");
  return res;
}