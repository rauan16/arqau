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

/** Format minor units as tenge string for display (e.g., "1,234 ₸"). */
export function formatMinorAsTenge(minor: number): string {
  const major = minorToMajor(minor);
  return `${major.toLocaleString("en-US")} ₸`;
}

/** Format major units (tenge) as string for display. */
export function formatTenge(value: number): string {
  return `${value.toLocaleString("en-US")} ₸`;
}

/** Parse user input string as major units (tenge) and convert to minor units. */
export function parseAmountInput(input: string): number {
  const major = Number(input);
  if (!Number.isFinite(major) || major < 0) return 0;
  return majorToMinor(major);
}
