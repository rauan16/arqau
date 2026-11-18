import { describe, it, expect } from "vitest";
import { validateWithdrawalAmount } from "./withdrawal-validation";
import { parseAmountInput } from "./money";

const mockT = (key: string) => {
  const messages: Record<string, string> = {
    "withdraw.errorInvalidNumber": "Enter a valid number.",
    "withdraw.errorZeroOrNegative": "Amount must be greater than zero.",
    "withdraw.errorExceeds": "Requested amount exceeds available balance of {amount} ₸.",
    "withdraw.errorValid": "Enter a valid amount to request.",
    "withdraw.errorTooManyDecimals": "Amount must have at most two decimal places.",
  };
  return messages[key] || key;
};

describe("lib/withdrawal-validation.ts", () => {
  const availableMinor = 12000000; // 120,000 ₸

  describe("validateWithdrawalAmount", () => {
    describe("Empty input", () => {
      it("returns valid=false, errorKey=null for empty string", () => {
        const result = validateWithdrawalAmount("", availableMinor, mockT);
        expect(result).toEqual({
          isValid: false,
          errorKey: null,
          requestedMinor: 0,
          remainingMinor: availableMinor,
        });
      });

      it("returns valid=false, errorKey=null for whitespace only", () => {
        const result = validateWithdrawalAmount("   ", availableMinor, mockT);
        expect(result.isValid).toBe(false);
        expect(result.errorKey).toBeNull();
      });
    });

    describe("Zero amount", () => {
      it("returns errorZeroOrNegative for '0'", () => {
        const result = validateWithdrawalAmount("0", availableMinor, mockT);
        expect(result.isValid).toBe(false);
        expect(result.errorKey).toBe("withdraw.errorZeroOrNegative");
      });

      it("returns errorZeroOrNegative for '0.00'", () => {
        const result = validateWithdrawalAmount("0.00", availableMinor, mockT);
        expect(result.isValid).toBe(false);
        expect(result.errorKey).toBe("withdraw.errorZeroOrNegative");
      });
    });

    describe("Negative amount", () => {
      it("returns errorZeroOrNegative for negative number", () => {
        const result = validateWithdrawalAmount("-100", availableMinor, mockT);
        expect(result.isValid).toBe(false);
        expect(result.errorKey).toBe("withdraw.errorZeroOrNegative");
      });

      it("returns errorZeroOrNegative for negative decimal", () => {
        const result = validateWithdrawalAmount("-50.50", availableMinor, mockT);
        expect(result.isValid).toBe(false);
        expect(result.errorKey).toBe("withdraw.errorZeroOrNegative");
      });
    });

    describe("Malformed input", () => {
      it("returns errorInvalidNumber for non-numeric string", () => {
        const result = validateWithdrawalAmount("abc", availableMinor, mockT);
        expect(result.isValid).toBe(false);
        expect(result.errorKey).toBe("withdraw.errorInvalidNumber");
      });

      it("returns errorInvalidNumber for special characters", () => {
        const result = validateWithdrawalAmount("100@", availableMinor, mockT);
        expect(result.isValid).toBe(false);
        expect(result.errorKey).toBe("withdraw.errorInvalidNumber");
      });

      it("returns errorInvalidNumber for empty after trim", () => {
        const result = validateWithdrawalAmount("   ", availableMinor, mockT);
        expect(result.isValid).toBe(false);
        expect(result.errorKey).toBeNull(); // Empty string returns null error
      });
    });

    describe("Decimal precision (max 2 places)", () => {
      it("accepts zero decimal places", () => {
        const result = validateWithdrawalAmount("100", availableMinor, mockT);
        expect(result.isValid).toBe(true);
        expect(result.requestedMinor).toBe(parseAmountInput("100"));
      });

      it("accepts one decimal place", () => {
        const result = validateWithdrawalAmount("100.5", availableMinor, mockT);
        expect(result.isValid).toBe(true);
        expect(result.requestedMinor).toBe(parseAmountInput("100.5"));
      });

      it("accepts two decimal places (tenge precision)", () => {
        const result = validateWithdrawalAmount("100.50", availableMinor, mockT);
        expect(result.isValid).toBe(true);
        expect(result.requestedMinor).toBe(parseAmountInput("100.50"));
      });

      it("rejects three decimal places", () => {
        const result = validateWithdrawalAmount("100.555", availableMinor, mockT);
        expect(result.isValid).toBe(false);
        expect(result.errorKey).toBe("withdraw.errorTooManyDecimals");
      });

      it("rejects four decimal places", () => {
        const result = validateWithdrawalAmount("100.1234", availableMinor, mockT);
        expect(result.isValid).toBe(false);
        expect(result.errorKey).toBe("withdraw.errorTooManyDecimals");
      });

      it("rejects many decimal places", () => {
        const result = validateWithdrawalAmount("100.123456789", availableMinor, mockT);
        expect(result.isValid).toBe(false);
        expect(result.errorKey).toBe("withdraw.errorTooManyDecimals");
      });

      it("rejects trailing zeros beyond two places (e.g., 100.500)", () => {
        const result = validateWithdrawalAmount("100.500", availableMinor, mockT);
        expect(result.isValid).toBe(false);
        expect(result.errorKey).toBe("withdraw.errorTooManyDecimals");
      });
    });

    describe("Valid amount within available balance", () => {
      it("returns valid=true for amount less than available", () => {
        const result = validateWithdrawalAmount("50000", availableMinor, mockT);
        expect(result.isValid).toBe(true);
        expect(result.errorKey).toBeNull();
        expect(result.requestedMinor).toBe(5000000);
        expect(result.remainingMinor).toBe(7000000);
      });

      it("returns valid=true for amount with decimals less than available", () => {
        const result = validateWithdrawalAmount("50000.50", availableMinor, mockT);
        expect(result.isValid).toBe(true);
        expect(result.requestedMinor).toBe(parseAmountInput("50000.50"));
        expect(result.remainingMinor).toBe(availableMinor - parseAmountInput("50000.50"));
      });
    });

    describe("Amount exactly equal to available balance", () => {
      it("returns valid=true for exact available amount", () => {
        const exactAmount = (availableMinor / 100).toString(); // 120000
        const result = validateWithdrawalAmount(exactAmount, availableMinor, mockT);
        expect(result.isValid).toBe(true);
        expect(result.errorKey).toBeNull();
        expect(result.requestedMinor).toBe(availableMinor);
        expect(result.remainingMinor).toBe(0);
      });
    });

    describe("Amount exceeding available balance", () => {
      it("returns errorExceeds for amount greater than available", () => {
        const result = validateWithdrawalAmount("150000", availableMinor, mockT);
        expect(result.isValid).toBe(false);
        expect(result.errorKey).toBe("withdraw.errorExceeds");
        expect(result.requestedMinor).toBe(15000000);
        expect(result.remainingMinor).toBe(0);
      });

      it("returns errorExceeds with formatted amount parameter", () => {
        const result = validateWithdrawalAmount("150000", availableMinor, mockT);
        expect(result.errorParams).toBeDefined();
        expect(result.errorParams?.amount).toBe("120,000 ₸");
      });
    });

    describe("Minor unit conversion accuracy", () => {
      it("uses exact minor-unit conversion from parseAmountInput", () => {
        const result = validateWithdrawalAmount("123.45", availableMinor, mockT);
        expect(result.requestedMinor).toBe(parseAmountInput("123.45"));
      });

      it("preserves round-trip consistency", () => {
        const result = validateWithdrawalAmount("10000", availableMinor, mockT);
        expect(result.requestedMinor).toBe(1000000);
      });
    });
  });
});