/**
 * CSRF protection tests for Next.js BFF auth endpoints.
 */
import { describe, it, expect, beforeEach, vi } from "vitest";
import { validateCsrfOrigin, getCsrfConfig, resetCsrfConfig, createCsrfErrorResponse } from "./csrf";

describe("lib/csrf.ts - CSRF Protection", () => {
  beforeEach(() => {
    resetCsrfConfig();
    vi.resetModules();
    // Set test environment variable
    process.env.NEXT_PUBLIC_APP_URL = "https://app.arqau.com";
  });

  describe("getCsrfConfig", () => {
    it("returns config with allowedOrigin from NEXT_PUBLIC_APP_URL", () => {
      const config = getCsrfConfig();
      expect(config.allowedOrigin).toBe("https://app.arqau.com");
    });

    it("caches the config", () => {
      const config1 = getCsrfConfig();
      const config2 = getCsrfConfig();
      expect(config1).toBe(config2);
    });

    it("throws when NEXT_PUBLIC_APP_URL is not set", () => {
      delete process.env.NEXT_PUBLIC_APP_URL;
      resetCsrfConfig();
      expect(() => getCsrfConfig()).toThrow("NEXT_PUBLIC_APP_URL environment variable is required");
    });

    it("throws when NEXT_PUBLIC_APP_URL is invalid", () => {
      process.env.NEXT_PUBLIC_APP_URL = "not-a-url";
      resetCsrfConfig();
      expect(() => getCsrfConfig()).toThrow("NEXT_PUBLIC_APP_URL must be a valid URL");
    });
  });

  describe("validateCsrfOrigin", () => {
    const mockRequest = (origin: string | null, host: string = "app.arqau.com") => {
      const headers = new Map<string, string>();
      if (origin !== null) headers.set("origin", origin);
      headers.set("host", host);

      return {
        headers: {
          get: (name: string) => headers.get(name.toLowerCase()) || null,
        },
      } as any;
    };

    it("accepts valid same-origin request", () => {
      const req = mockRequest("https://app.arqau.com");
      const result = validateCsrfOrigin(req);
      expect(result.valid).toBe(true);
    });

    it("rejects cross-origin request", () => {
      const req = mockRequest("https://evil.com");
      const result = validateCsrfOrigin(req);
      expect(result.valid).toBe(false);
      expect(result.error).toBe("Invalid Origin");
    });

    it("rejects request with missing Origin header", () => {
      const req = mockRequest(null);
      const result = validateCsrfOrigin(req);
      expect(result.valid).toBe(false);
      expect(result.error).toBe("Missing Origin header");
    });

    it("rejects request with null Origin", () => {
      const req = mockRequest(null);
      const result = validateCsrfOrigin(req);
      expect(result.valid).toBe(false);
    });

    it("rejects malformed Origin header", () => {
      const req = mockRequest("not-a-url");
      const result = validateCsrfOrigin(req);
      expect(result.valid).toBe(false);
      expect(result.error).toBe("Invalid Origin header");
    });

    it("rejects Origin with different scheme", () => {
      const req = mockRequest("http://app.arqau.com"); // HTTP vs HTTPS
      const result = validateCsrfOrigin(req);
      expect(result.valid).toBe(false);
    });

    it("rejects Origin with different port", () => {
      const req = mockRequest("https://app.arqau.com:8080");
      const result = validateCsrfOrigin(req);
      expect(result.valid).toBe(false);
    });

    it("rejects spoofed Host header - origin compared to configured value", () => {
      // Even if Host header is spoofed to "app.arqau.com",
      // the Origin must match the configured NEXT_PUBLIC_APP_URL
      const req = mockRequest("https://evil.com", "app.arqau.com");
      const result = validateCsrfOrigin(req);
      expect(result.valid).toBe(false);
    });

    it("rejects subdomain", () => {
      const req = mockRequest("https://sub.app.arqau.com");
      const result = validateCsrfOrigin(req);
      expect(result.valid).toBe(false);
    });

    it("rejects www subdomain", () => {
      const req = mockRequest("https://www.app.arqau.com");
      const result = validateCsrfOrigin(req);
      expect(result.valid).toBe(false);
    });
  });

  describe("createCsrfErrorResponse", () => {
    it("returns 403 response with error message", async () => {
      const response = createCsrfErrorResponse("Invalid Origin");
      expect(response.status).toBe(403);
      expect(response.headers.get("Content-Type")).toBe("application/json");
      expect(response.headers.get("Cache-Control")).toBe("no-store, private");
      const body = await response.json();
      expect(body.error).toBe("Invalid Origin");
    });
  });

  describe("resetCsrfConfig", () => {
    it("allows config to be reloaded after env change", () => {
      const config1 = getCsrfConfig();
      process.env.NEXT_PUBLIC_APP_URL = "https://different.com";
      resetCsrfConfig();
      const config2 = getCsrfConfig();
      expect(config2.allowedOrigin).toBe("https://different.com");
    });
  });
});