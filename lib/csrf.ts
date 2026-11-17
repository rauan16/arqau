/**
 * CSRF protection for cookie-authenticated BFF endpoints.
 *
 * Security model:
 * - Only state-changing endpoints (POST) that use cookie authentication need CSRF protection
 * - We validate the Origin header against an explicitly configured frontend origin
 * - We do NOT trust Host, X-Forwarded-Host, or any client-controlled headers
 * - Missing Origin is REJECTED for mutating operations (browsers always send Origin for cross-origin requests)
 * - The expected origin is derived from NEXT_PUBLIC_APP_URL (explicit, deployment-time configuration)
 */

import { NextRequest } from "next/server";

interface CsrfConfig {
  allowedOrigin: string;
}

let _config: CsrfConfig | null = null;

export function getCsrfConfig(): CsrfConfig {
  if (_config) return _config;

  const appUrl = process.env.NEXT_PUBLIC_APP_URL;
  if (!appUrl) {
    throw new Error(
      "NEXT_PUBLIC_APP_URL environment variable is required for CSRF protection. " +
      "Set it to the frontend origin (e.g., https://app.arqau.com)."
    );
  }

  try {
    const url = new URL(appUrl);
    // Ensure we have a valid origin (scheme + host)
    if (!url.protocol || !url.host) {
      throw new Error("Invalid NEXT_PUBLIC_APP_URL");
    }
    _config = { allowedOrigin: `${url.protocol}//${url.host}` };
  } catch {
    throw new Error("NEXT_PUBLIC_APP_URL must be a valid URL with scheme and host");
  }

  return _config;
}

/**
 * Resolves the configured allowed origin, or null when NEXT_PUBLIC_APP_URL is
 * not set. Never throws: callers decide how to handle a missing configuration.
 */
function resolveConfiguredOrigin(): CsrfConfig | null {
  try {
    return getCsrfConfig();
  } catch {
    return null;
  }
}

function isLoopbackOrigin(origin: string): boolean {
  try {
    const { hostname } = new URL(origin);
    return hostname === "localhost" || hostname === "127.0.0.1" || hostname === "::1";
  } catch {
    return false;
  }
}

export function validateCsrfOrigin(request: NextRequest): { valid: boolean; error?: string } {
  const configured = resolveConfiguredOrigin();
  const origin = request.headers.get("origin");

  // Missing Origin is a hard failure for cookie-authenticated mutating endpoints
  // Browsers always send Origin for cross-origin requests; same-origin requests
  // from the browser also include Origin in modern browsers.
  if (!origin) {
    return { valid: false, error: "Missing Origin header" };
  }

  // Validate origin format
  let originUrl: URL;
  try {
    originUrl = new URL(origin);
  } catch {
    return { valid: false, error: "Invalid Origin header" };
  }

  // Compare against explicitly configured allowed origin
  if (configured) {
    if (origin !== configured.allowedOrigin) {
      return { valid: false, error: "Invalid Origin" };
    }
    return { valid: true };
  }

  // No NEXT_PUBLIC_APP_URL configured. In development this is the common case,
  // so allow only a same-origin call from a loopback origin: the browser must
  // report an Origin that is loopback AND identical to the origin the request
  // was sent to. Every other case fails closed, including all of production,
  // where a missing configuration is a deployment error and never a silent
  // bypass. The cookie this guard protects is httpOnly, SameSite=Lax and
  // path-scoped, so it is only ever attached to such same-origin requests.
  if (process.env.NODE_ENV === "production") {
    return { valid: false, error: "CSRF origin is not configured" };
  }
  if (!isLoopbackOrigin(origin)) {
    return { valid: false, error: "Invalid Origin" };
  }
  const requestOrigin = request.nextUrl?.origin;
  if (!requestOrigin || origin !== requestOrigin) {
    return { valid: false, error: "Invalid Origin" };
  }
  return { valid: true };
}

/**
 * Route-handler guard: returns an error Response when the request must be
 * rejected, or null when it may proceed. Never throws, so a broken CSRF
 * configuration surfaces as a JSON error instead of an unhandled HTML 500.
 */
export function csrfGuard(request: NextRequest): Response | null {
  let result: { valid: boolean; error?: string };
  try {
    result = validateCsrfOrigin(request);
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : "CSRF configuration error";
    return new Response(JSON.stringify({ error: message }), {
      status: 503,
      headers: { "Content-Type": "application/json", "Cache-Control": "no-store, private" },
    });
  }
  if (!result.valid) {
    return createCsrfErrorResponse(result.error || "Invalid Origin");
  }
  return null;
}

export function createCsrfErrorResponse(error: string) {
  return new Response(
    JSON.stringify({ error }),
    {
      status: 403,
      headers: {
        "Content-Type": "application/json",
        "Cache-Control": "no-store, private",
      },
    }
  );
}

// Reset for testing only
export function resetCsrfConfig() {
  _config = null;
}