import { parseAmountInput, formatMinorAsTenge } from "./money";
import type { EWAResultResponse } from "./api";

export interface WithdrawalValidationResult {
  isValid: boolean;
  errorKey: string | null;
  requestedMinor: number;
  remainingMinor: number;
  errorParams?: Record<string, string>;
}

function hasMoreThanTwoDecimals(value: string): boolean {
  const trimmed = value.trim();
  const decimalIndex = trimmed.indexOf(".");
  if (decimalIndex === -1) return false;
  return trimmed.length - decimalIndex - 1 > 2;
}

export function validateWithdrawalAmount(
  value: string,
  availableMinor: number,
  t: (key: string) => string
): WithdrawalValidationResult {
  if (value === "" || value.trim() === "") {
    return { isValid: false, errorKey: null, requestedMinor: 0, remainingMinor: availableMinor };
  }

  if (hasMoreThanTwoDecimals(value)) {
    return { isValid: false, errorKey: "withdraw.errorTooManyDecimals", requestedMinor: 0, remainingMinor: availableMinor };
  }

  const major = Number(value);
  if (!Number.isFinite(major) || isNaN(major)) {
    return { isValid: false, errorKey: "withdraw.errorInvalidNumber", requestedMinor: 0, remainingMinor: availableMinor };
  }

  if (major <= 0) {
    return { isValid: false, errorKey: "withdraw.errorZeroOrNegative", requestedMinor: 0, remainingMinor: availableMinor };
  }

  const requestedMinor = parseAmountInput(value);
  if (requestedMinor > availableMinor) {
    return {
      isValid: false,
      errorKey: "withdraw.errorExceeds",
      requestedMinor,
      remainingMinor: 0,
      errorParams: { amount: formatMinorAsTenge(availableMinor) },
    };
  }

  return { isValid: true, errorKey: null, requestedMinor, remainingMinor: availableMinor - requestedMinor };
}

export function createValidationHelper(
  t: (key: string) => string,
  getAvailableMinor: () => number
) {
  return (value: string): WithdrawalValidationResult => {
    return validateWithdrawalAmount(value, getAvailableMinor(), t);
  };
}