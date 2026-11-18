// ---------------------------------------------------------------------------
// Demo adapter.
//
// The public demo renders the *same* dashboard components as the authenticated
// home page. Those components consume backend contracts
// (EWAResultResponse / Transaction / FinancialContext / WithdrawalDecisionResponse),
// so this module maps the local demo state onto exactly those shapes. Nothing
// here talks to the network and no value is invented: every number is derived
// from the demo store seed and its existing formulas.
// ---------------------------------------------------------------------------

import { locales, Locale } from "./i18n";
import {
  EWAResultResponse,
  FinancialContext,
  Transaction,
  WithdrawalDecisionResponse,
} from "./api";
import {
  computeCurrentPeriodCategories,
  computeCurrentPeriodTotals,
  computeDemoSavings,
  computeUpcomingTotal,
  computeUpcomingUnpaidTotal,
  evaluateDemoScenario,
  type DemoState,
} from "./demoStore";

/** 1 tenge = 100 tiyin (minor units), matching the backend contracts. */
const MINOR = 100;

/** The demo pay period is a monthly cycle, matching a monthly salary. */
const PERIOD_DAYS = 31;

const DEMO_USER_ID = "demo";

function isoAddDays(iso: string, days: number): string {
  const [year, month, day] = iso.split("-").map(Number);
  const date = new Date(Date.UTC(year, month - 1, day + days));
  return date.toISOString().slice(0, 10);
}

export interface DemoOverview {
  /** Shaped like the authenticated EWA calculation, in minor units. */
  calculation: EWAResultResponse;
  /** Shaped like the authenticated transaction list, in minor units. */
  transactions: Transaction[];
  /** Shaped like the authenticated financial context, in minor units. */
  context: FinancialContext;
  /** Amount of the current pay period left, in tenge. */
  daysToPayday: number;
  /** Amount that keeps bills and the reserve intact, in tenge (demo plan). */
  comfortableWithdrawal: number;
  /** Upcoming bills total, in tenge. */
  upcomingBillsTotal: number;
  /** Reserve target, in tenge. */
  reserveTarget: number;
}

/**
 * Maps the demo state onto the authenticated overview contracts.
 *
 * The pay period is derived from the demo store itself: it starts at
 * `paydayDate`, spans 30 days, and the "today" of the scenario is placed so the
 * remaining days equal the store's `daysToPayday`. No date is invented.
 */
export function buildDemoOverview(state: DemoState): DemoOverview {
  const periodStart = state.paydayDate;
  const periodEnd = isoAddDays(periodStart, PERIOD_DAYS - 1);
  const nextPayday = isoAddDays(periodStart, PERIOD_DAYS);
  const daysToPayday = Math.min(Math.max(0, Math.round(state.daysToPayday)), PERIOD_DAYS - 1);
  const calculationDate = isoAddDays(nextPayday, -daysToPayday);

  const currentPeriod = computeCurrentPeriodTotals(state);
  const currentPeriodCategories = computeCurrentPeriodCategories(state);
  const upcomingBillsTotal = computeUpcomingTotal();
  // Same canonical rule as computeDemoPlan (demoStore) and evaluateDemoScenario:
  // comfortable = available - unpaid bills - reserve target. Using the bills
  // *total* here instead of the unpaid total would count already-paid bills
  // twice (they were already deducted from earned), and substituting
  // savings.remaining for reserveTarget would double-count the reserve when
  // savings are partial. Both inputs come from the same authoritative state.
  const comfortableWithdrawal = Math.max(
    0,
    state.available - computeUpcomingUnpaidTotal() - state.reserveTarget,
  );
  // The demo always fills the schema the view expects; the store's own
  // `earned` and `available` values keep their existing meaning.
  const earned = state.earned;
  const available = state.available;

  const calculation: EWAResultResponse = {
    salary_amount_minor: Math.round(state.salary * MINOR),
    earned_amount_minor: Math.round(earned * MINOR),
    policy_limit_minor: 0,
    reserved_amount_minor: 0,
    paid_amount_minor: Math.round(Math.max(0, earned - available) * MINOR),
    available_amount_minor: Math.round(available * MINOR),
    pay_period_start: `${periodStart}T00:00:00`,
    pay_period_end: `${periodEnd}T00:00:00`,
    calculation_date: `${calculationDate}T00:00:00`,
    eligible: available > 0,
    eligibility_reasons: [],
    minimum_withdrawal_minor: null,
    maximum_withdrawal_minor: null,
    // A demo never creates a real request.
    can_request_withdrawal: false,
    max_withdrawals_per_period: null,
    withdrawals_this_period: 0,
    max_requestable_amount_minor: Math.round(available * MINOR),
  };

  const transactions: Transaction[] = state.transactions.map((tx) => ({
    id: tx.id,
    user_id: DEMO_USER_ID,
    type: tx.type,
    amount_minor: Math.round(tx.amount * MINOR),
    category: tx.category,
    merchant: tx.merchant,
    description: tx.description,
    date: `${tx.date}T00:00:00`,
  }));

  const expenseCount = state.transactions.filter((tx) => tx.type === "expense").length;
  const currentExpenseMinor = Math.round(currentPeriod.expense * MINOR);

  const context: FinancialContext = {
    user_id: DEMO_USER_ID,
    generated_at: `${calculationDate}T00:00:00`,
    calculation_date: calculationDate,
    employment: {
      employment_id: null,
      employer_id: null,
      employer_name: null,
      employment_status: "demo",
    },
    income: {
      salary_amount_minor: Math.round(state.salary * MINOR),
      currency: "KZT",
      pay_period_start: periodStart,
      pay_period_end: periodEnd,
    },
    ewa: {
      earned_amount_minor: calculation.earned_amount_minor,
      policy_limit_minor: 0,
      reserved_amount_minor: 0,
      paid_amount_minor: calculation.paid_amount_minor,
      available_amount_minor: calculation.available_amount_minor,
      max_requestable_amount_minor: calculation.max_requestable_amount_minor,
      pay_period_start: periodStart,
      pay_period_end: periodEnd,
      calculation_date: calculationDate,
      salary_amount_minor: calculation.salary_amount_minor,
      eligible: calculation.eligible,
      eligibility_reasons: [],
      minimum_withdrawal_minor: null,
      maximum_withdrawal_minor: null,
      can_request_withdrawal: false,
      max_withdrawals_per_period: null,
      withdrawals_this_period: 0,
    },
    withdrawal_history: {
      available: true,
      total_requests: 0,
      pending_count: 0,
      approved_count: 0,
      paid_count: 0,
      rejected_count: 0,
      cancelled_count: 0,
      requested_amount_minor: 0,
      paid_amount_minor: 0,
      // The demo has no withdrawal requests, so activity shows no requests.
      recent_requests: [],
    },
    spending: {
      available: currentPeriod.expense > 0,
      total_spending_minor: currentExpenseMinor,
      transaction_count: expenseCount,
      essential_spending_minor: null,
      discretionary_spending_minor: null,
      category_breakdown: currentPeriodCategories.map((row) => ({
        category: row.category,
        amount_minor: Math.round(row.amount * MINOR),
        transaction_count: Math.max(1, Math.round(row.share * expenseCount)),
      })),
    },
    budget: {
      available: false,
      total_budget_minor: null,
      spent_minor: null,
      remaining_minor: null,
    },
    goals: {
      available: false,
      active_goals_count: 0,
      total_target_minor: null,
      total_saved_minor: null,
      goals: [],
    },
    data_quality: {
      has_salary_profile: state.salary > 0,
      has_ewa_policy: false,
      has_transactions: state.transactions.length > 0,
      has_budget: false,
      has_goals: false,
      missing_data: [],
    },
  };

  return {
    calculation,
    transactions,
    context,
    daysToPayday,
    comfortableWithdrawal,
    upcomingBillsTotal,
    reserveTarget: state.reserveTarget,
  };
}

/**
 * Builds the analysis result for a demo amount using the demo store's own
 * scenario engine. It is a purely local, deterministic evaluation: it never
 * calls an endpoint and never changes the demo state.
 */
export function buildDemoDecision(state: DemoState, amount: number, locale: Locale): WithdrawalDecisionResponse {
  const d = locales[locale].demo;
  const scenario = evaluateDemoScenario(state, amount);
  const savings = computeDemoSavings(state);
  const upcomingBillsTotal = computeUpcomingTotal();
  const fmt = (value: number) => value.toLocaleString(locale === "ru" ? "ru-RU" : "en-US");

  const statusText =
    scenario.status === "comfortable" ? d.comfortableText : scenario.status === "caution" ? d.cautionText : d.highRiskText;
  const requestable = amount > 0 && amount <= state.available && scenario.bufferAfter >= 0;

  return {
    requested_amount_minor: Math.round(amount * MINOR),
    requestable,
    blocking_reasons: requestable ? [] : [statusText],
    current_available_amount_minor: Math.round(state.available * MINOR),
    max_requestable_amount_minor: Math.round(state.available * MINOR),
    snapshot_only: true,
    decision: {
      summary: statusText,
      status_explanation: statusText,
      key_facts: [
        { code: "available", text: `${d.available}: ${fmt(state.available)} ₸` },
        { code: "upcoming-bills", text: `${d.upcomingBills}: ${fmt(upcomingBillsTotal)} ₸` },
        { code: "periodSurplus", text: `${d.periodSurplus}: ${fmt(savings.saved)} / ${fmt(savings.target)} ₸` },
      ],
      considerations: [],
      options: [],
      data_limitations: [d.persistentBadgeLong],
      disclaimer: d.scenariosNote,
      // Demo analysis is local: no AI provider produced this.
      ai_metadata: { generated: false, fallback_used: false, provider: null, model: null },
    },
  };
}
