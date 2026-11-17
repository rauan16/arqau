// ---------------------------------------------------------------------------
// Unified demo financial context.
//
// Single source of truth for the demo's financial state. Every surface
// (dashboard, what-if, get-money, future AI chat) reads from this context
// instead of recomputing or duplicating figures.
//
// Design rules:
// - Available EWA capacity, earned salary, income, expense and reserve are
//   kept as separate fields; none is aliased into another.
// - Each transaction contributes to totals exactly once.
// - Upcoming bills carry due dates and payment state so they can be tracked
//   without double counting against the reserve.
// - Everything is computed from `lib/demoStore` state; nothing talks to the
//   network and nothing mutates real accounts.
// ---------------------------------------------------------------------------

import {
  computeCurrentPeriodTotals,
  computeDemoSavings,
  computeDemoTotals,
  evaluateDemoScenario,
  type DemoBill,
  type DemoState,
  upcomingBills,
  computeUpcomingTotal,
} from "./demoStore";
import { Locale } from "./i18n";

/** Tenge (major units). All monetary fields in this context are in tenge. */
export const DEMO_CURRENCY = "KZT";

/** Source marker so the context can never be confused with an authenticated account. */
export type DemoDataSource = "demo";

/** Status of a hypothetical amount against bills and reserve. */
export type DemoAffordabilityStatus = "comfortable" | "caution" | "high-risk";

export interface DemoFinancialContext {
  /** Amount currently requestable from already-earned wages (EWA capacity). */
  availableAmount: number;
  /** Total earned this pay period. */
  earnedAmount: number;
  /** Salary for the current period. */
  salaryAmount: number;
  /** Income posted in the current pay period. */
  incomeAmount: number;
  /** Expense posted in the current pay period. */
  expenseAmount: number;
  /** Income minus expense for the current pay period. */
  netAmount: number;
  /** Upcoming mandatory bills with due dates and payment state. */
  upcomingBills: DemoBill[];
  /** Total of all upcoming bills (paid and unpaid). */
  upcomingBillsTotal: number;
  /** Total of upcoming bills that are not yet paid. */
  upcomingBillsUnpaidTotal: number;
  /** Target reserve amount. */
  reserveTarget: number;
  /** Amount already set aside toward the reserve this period. */
  reserveSaved: number;
  /** Reserve target minus amount saved (capped at 0). */
  reserveRemaining: number;
  /** Reserve progress, 0 to 1. */
  reserveProgress: number;
  /** ISO date of the next payday. */
  paydayDate: string;
  /** Days until the next payday. */
  daysToPayday: number;
  /** Currency of all amounts. */
  currency: string;
  /** ISO date when this snapshot was computed. */
  dataAsOf: string;
  /** Always "demo" — never an authenticated account. */
  source: DemoDataSource;
  /** Always true for this context. */
  isDemo: boolean;
  /** Human-readable warnings about incomplete or stale data. */
  warnings: string[];
}

/** Result of evaluating a hypothetical withdrawal or purchase amount. */
export interface DemoAffordabilityResult {
  amount: number;
  status: DemoAffordabilityStatus;
  /** Balance left after the amount. */
  remainingAvailable: number;
  /** Balance left after the amount and all unpaid upcoming bills. */
  bufferAfterBills: number;
  /** Whether the amount can be requested without violating reserve or bills. */
  requestable: boolean;
  /** Share of earned amount this represents, 0 to 1. */
  shareOfEarned: number;
  /** Human-readable reason when not requestable. */
  reason?: string;
}

/** Build the unified financial context from the demo store state. */
export function buildDemoFinancialContext(state: DemoState, locale: Locale = "ru"): DemoFinancialContext {
  const totals = computeDemoTotals(state);
  const currentPeriod = computeCurrentPeriodTotals(state);
  const savings = computeDemoSavings(state);
  const bills = upcomingBills(locale);
  const billsTotal = computeUpcomingTotal();
  const billsUnpaidTotal = bills.filter((b) => !b.isPaid).reduce((sum, b) => sum + b.amount, 0);

  const warnings: string[] = [];
  if (state.available <= 0) {
    warnings.push("No EWA capacity is currently available.");
  }
  if (billsUnpaidTotal > 0 && state.available < billsUnpaidTotal) {
    warnings.push("Available amount does not cover unpaid upcoming bills.");
  }
  if (savings.progress < 1) {
    warnings.push(`Reserve is below target by ${savings.remaining} tenge.`);
  }

  return {
    availableAmount: state.available,
    earnedAmount: state.earned,
    salaryAmount: state.salary,
    incomeAmount: currentPeriod.income,
    expenseAmount: currentPeriod.expense,
    netAmount: currentPeriod.net,
    upcomingBills: bills,
    upcomingBillsTotal: billsTotal,
    upcomingBillsUnpaidTotal: billsUnpaidTotal,
    reserveTarget: state.reserveTarget,
    reserveSaved: savings.saved,
    reserveRemaining: savings.remaining,
    reserveProgress: savings.progress,
    paydayDate: state.paydayDate,
    daysToPayday: state.daysToPayday,
    currency: DEMO_CURRENCY,
    dataAsOf: new Date().toISOString(),
    source: "demo",
    isDemo: true,
    warnings,
  };
}

/** Evaluate a hypothetical amount against available, bills and reserve. */
export function evaluateDemoAffordability(
  state: DemoState,
  amount: number,
  locale: Locale = "ru",
): DemoAffordabilityResult {
  const scenario = evaluateDemoScenario(state, amount);
  const context = buildDemoFinancialContext(state, locale);

  const remainingAvailable = Math.max(0, context.availableAmount - amount);
  const bufferAfterBills = remainingAvailable - context.upcomingBillsUnpaidTotal;

  let status: DemoAffordabilityStatus;
  if (bufferAfterBills >= context.reserveTarget) status = "comfortable";
  else if (bufferAfterBills >= 0) status = "caution";
  else status = "high-risk";

  const requestable = amount > 0 && amount <= context.availableAmount && bufferAfterBills >= 0;

  return {
    amount,
    status,
    remainingAvailable,
    bufferAfterBills,
    requestable,
    shareOfEarned: context.earnedAmount > 0 ? Math.min(1, amount / context.earnedAmount) : 0,
    reason: requestable
      ? undefined
      : status === "high-risk"
        ? "This amount would leave upcoming bills uncovered."
        : status === "caution"
          ? "This amount would reduce your reserve below target."
          : "Amount is not requestable.",
  };
}
