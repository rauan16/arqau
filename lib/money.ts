/**
 * Minor unit (tiyin) conversion utilities.
 *
 * Backend stores all monetary values as integer minor units (1 tenge = 100 tiyin).
 * Frontend user input and display work in tenge (major units).
 * These utilities handle the conversion.
 */

export const MINOR_UNITS_PER_MAJOR = 100;

/** Convert minor units (tiyin) to major units (tenge) for display. */
export function minorToMajor(minor: number): number {
  return minor / MINOR_UNITS_PER_MAJOR;
}

/** Convert major units (tenge) to minor units (tiyin) for API requests. */
export function majorToMinor(major: number): number {
  return Math.round(major * MINOR_UNITS_PER_MAJOR);
}

/**
 * Format minor units as tenge string for display (e.g., "1,234 ₸").
 *
 * Defaults to English grouping so existing callers keep their current output.
 * Pass "ru" for the Russian grouping used by the dashboard references
 * (e.g. "1 234 ₸" with a non-breaking space).
 */
export function formatMinorAsTenge(minor: number, locale: "en" | "ru" = "en"): string {
  const major = minorToMajor(minor);
  return `${major.toLocaleString(locale === "ru" ? "ru-RU" : "en-US")} ₸`;
}

/** Format major units (tenge) as string for display. */
export function formatTenge(value: number): string {
  return `${value.toLocaleString("en-US")} ₸`;
}

/**
 * Format major units (tenge) as string for display with locale support.
 * Uses the same grouping conventions as the rest of the application.
 */
export function formatMajorAsTenge(value: number, locale: "en" | "ru" = "en"): string {
  return `${value.toLocaleString(locale === "ru" ? "ru-RU" : "en-US")} ₸`;
}

/** Compact chart-axis label for a minor-unit amount (e.g. 2500000 -> "25k"). */
export function compactTenge(minor: number): string {
  const major = minorToMajor(minor);
  if (Math.abs(major) >= 1000) {
    const thousands = major / 1000;
    const rounded = Math.abs(thousands) >= 100 ? Math.round(thousands) : Math.round(thousands * 10) / 10;
    return `${rounded}k`;
  }
  return `${Math.round(major)}`;
}

/** Parse user input string as major units (tenge) and convert to minor units. */
export function parseAmountInput(input: string): number {
  const major = Number(input);
  if (!Number.isFinite(major) || major < 0) return 0;
  return majorToMinor(major);
}
