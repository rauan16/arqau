import { describe, it, expect } from "vitest";
import { minorToMajor, majorToMinor, formatMinorAsTenge, formatTenge, parseAmountInput, MINOR_UNITS_PER_MAJOR } from "./money";

describe("lib/money.ts - Minor unit conversions", () => {
  describe("MINOR_UNITS_PER_MAJOR", () => {
    it("is 100 (1 tenge = 100 tiyin)", () => {
      expect(MINOR_UNITS_PER_MAJOR).toBe(100);
    });
  });

  describe("minorToMajor", () => {
    it("converts 0 minor units to 0 tenge", () => {
      expect(minorToMajor(0)).toBe(0);
    });

    it("converts 1 minor unit to 0.01 tenge", () => {
      expect(minorToMajor(1)).toBe(0.01);
    });

    it("converts 100 minor units to 1 tenge", () => {
      expect(minorToMajor(100)).toBe(1);
    });

    it("converts 12345 minor units to 123.45 tenge", () => {
      expect(minorToMajor(12345)).toBe(123.45);
    });

    it("converts 30000000 minor units to 300000 tenge", () => {
      expect(minorToMajor(30000000)).toBe(300000);
    });
  });

  describe("majorToMinor", () => {
    it("converts 0 tenge to 0 minor units", () => {
      expect(majorToMinor(0)).toBe(0);
    });

    it("converts 1 tenge to 100 minor units", () => {
      expect(majorToMinor(1)).toBe(100);
    });

    it("converts 123.45 tenge to 12345 minor units", () => {
      expect(majorToMinor(123.45)).toBe(12345);
    });

    it("converts 300000 tenge to 30000000 minor units", () => {
      expect(majorToMinor(300000)).toBe(30000000);
    });

    it("rounds correctly for fractional tenge", () => {
      expect(majorToMinor(10.555)).toBe(1056);
    });
  });

  describe("formatMinorAsTenge", () => {
    it("formats 0 as '0 ₸'", () => {
      expect(formatMinorAsTenge(0)).toBe("0 ₸");
    });

    it("formats 100 as '1 ₸'", () => {
      expect(formatMinorAsTenge(100)).toBe("1 ₸");
    });

    it("formats 12345 as '123.45 ₸'", () => {
      expect(formatMinorAsTenge(12345)).toBe("123.45 ₸");
    });

    it("formats 30000000 as '300,000 ₸'", () => {
      expect(formatMinorAsTenge(30000000)).toBe("300,000 ₸");
    });

    it("formats 12345678 as '123,456.78 ₸'", () => {
      expect(formatMinorAsTenge(12345678)).toBe("123,456.78 ₸");
    });
  });

  describe("formatTenge (major units)", () => {
    it("formats 0 as '0 ₸'", () => {
      expect(formatTenge(0)).toBe("0 ₸");
    });

    it("formats 100 as '100 ₸'", () => {
      expect(formatTenge(100)).toBe("100 ₸");
    });

    it("formats 300000 as '300,000 ₸'", () => {
      expect(formatTenge(300000)).toBe("300,000 ₸");
    });
  });

  describe("parseAmountInput", () => {
    it("parses '0' as 0 minor units", () => {
      expect(parseAmountInput("0")).toBe(0);
    });

    it("parses '1' as 100 minor units", () => {
      expect(parseAmountInput("1")).toBe(100);
    });

    it("parses '100' as 10000 minor units", () => {
      expect(parseAmountInput("100")).toBe(10000);
    });

    it("parses '123.45' as 12345 minor units", () => {
      expect(parseAmountInput("123.45")).toBe(12345);
    });

    it("parses '300000' as 30000000 minor units", () => {
      expect(parseAmountInput("300000")).toBe(30000000);
    });

    it("returns 0 for empty string", () => {
      expect(parseAmountInput("")).toBe(0);
    });

    it("returns 0 for invalid input", () => {
      expect(parseAmountInput("abc")).toBe(0);
    });

    it("returns 0 for negative numbers", () => {
      expect(parseAmountInput("-100")).toBe(0);
    });
  });

  describe("Round-trip consistency", () => {
    it("minor -> major -> minor preserves value for whole tenge", () => {
      const minor = 50000;
      const major = minorToMajor(minor);
      const back = majorToMinor(major);
      expect(back).toBe(minor);
    });

    it("major -> minor -> major preserves value", () => {
      const major = 12345;
      const minor = majorToMinor(major);
      const back = minorToMajor(minor);
      expect(back).toBe(major);
    });
  });
});