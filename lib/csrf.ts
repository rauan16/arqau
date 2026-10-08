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

export function validateCsrfOrigin(request: NextRequest): { valid: boolean; error?: string } {
  const config = getCsrfConfig();
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
  if (origin !== config.allowedOrigin) {
    return { valid: false, error: "Invalid Origin" };
  }

  return { valid: true };
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