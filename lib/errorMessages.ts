/**
 * Turns a backend error payload into a single readable sentence.
 *
 * FastAPI validation errors are returned as `{ detail: [{ msg, loc, ... }] }`,
 * while our own endpoints return `{ detail: "message" }` or `{ error: "..." }`.
 * Rendering the raw shape would leak structure (or "[object Object]") into the
 * UI, so every layer normalizes to one human sentence before display.
 */
export function toReadableError(payload: unknown, fallback: string): string {
  if (typeof payload === "string" && payload.trim()) {
    return payload.trim();
  }

  if (Array.isArray(payload)) {
    const parts = payload
      .map((item) => {
        if (typeof item === "string") return item;
        if (item && typeof item === "object") {
          const record = item as { msg?: unknown; message?: unknown; detail?: unknown };
          if (typeof record.msg === "string") return record.msg;
          if (typeof record.message === "string") return record.message;
          if (typeof record.detail === "string") return record.detail;
        }
        return null;
      })
      .filter((value): value is string => Boolean(value));
    if (parts.length > 0) {
      return parts.join(". ");
    }
  }

  if (payload && typeof payload === "object") {
    const record = payload as { message?: unknown; msg?: unknown; error?: unknown };
    if (typeof record.message === "string") return record.message;
    if (typeof record.msg === "string") return record.msg;
    if (typeof record.error === "string") return record.error;
  }

  return fallback;
}
