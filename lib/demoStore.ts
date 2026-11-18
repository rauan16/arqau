// ---------------------------------------------------------------------------
// Investor demo mode
//
// A single, internally consistent, deterministic dataset. Nothing here talks to
// the network: no account is created, no token is read or written, and no real
// financial endpoint can be reached from this module.
//
// Storage is namespaced under its own key and never shares the keys used by the
// authenticated app (`arqau_token`, `arqau-onboarding-profile`,
// `arqau-financial-data`), so demo edits can never overwrite real data.
// ---------------------------------------------------------------------------

import { locales, Locale } from "./i18n";
import { formatMajorAsTenge } from "./money";
import { useSyncExternalStore } from "react";

export const demoStorageKey = "arqau-demo-state";
const DEMO_STATE_VERSION = 1;

export type DemoTransactionType = "income" | "expense";

export interface DemoBill {
  id: string;
  label: string;
  amount: number;
  dueDate: string;
  isPaid: boolean;
}

export interface DemoTransaction {
  id: string;
  type: DemoTransactionType;
  /** Amount in tenge (major units), which is what the demo editor works in. */
  amount: number;
  category: string;
  merchant?: string;
  description?: string;
  /** ISO date (YYYY-MM-DD). */
  date: string;
}

export interface DemoState {
  version: number;
  transactions: DemoTransaction[];
  /** Amount currently requestable from already-earned wages, in tenge. */
  available: number;
  /** Total earned this pay period, in tenge. */
  earned: number;
  /** Salary for the period, in tenge. */
  salary: number;
  /** Target reserve, in tenge. */
  reserveTarget: number;
  /** Number of days until the next payday. */
  daysToPayday: number;
  /** Payday date of the current period, ISO date. */
  paydayDate: string;
}

/**
 * The seed is the only source of initial numbers. Every derived figure the UI
 * shows (totals, category breakdowns, remaining balance, plan projection and
 * scenario results) is computed from these transactions and these constants,
 * so nothing can drift out of reconciliation.
 *
 * Dates are relative to `paydayDate` so the scenario stays coherent without a
 * fixed calendar year.
 */
export function createSeedDemoState(): DemoState {
  const paydayDate = "2026-10-16";

  const transactions: DemoTransaction[] = [
    // --- Current period (16 Oct – 16 Nov) ---
    { id: "seed-1", type: "income", amount: 150000, category: "Salary", merchant: "Employer payroll", date: "2026-09-16", description: "Advance paid on payday" },
    { id: "seed-2", type: "expense", amount: 45000, category: "Housing", merchant: "Home Rent", date: "2026-09-17" },
    { id: "seed-3", type: "expense", amount: 25000, category: "Food", merchant: "City Market", date: "2026-09-21" },
    { id: "seed-4", type: "expense", amount: 15000, category: "Transport", merchant: "Metro Pass", date: "2026-09-25" },
    { id: "seed-5", type: "income", amount: 37400, category: "Salary", merchant: "Employer payroll", date: "2026-10-02", description: "Second payday of the cycle" },
    { id: "seed-6", type: "expense", amount: 12400, category: "Food", merchant: "City Market", date: "2026-10-05" },
    { id: "seed-7", type: "expense", amount: 6500, category: "Lifestyle", merchant: "Streaming Plus", date: "2026-10-07" },
    { id: "seed-8", type: "expense", amount: 13000, category: "Health", merchant: "Pharmacy", date: "2026-10-09" },

    // --- New period (16 Oct – 25 Oct demo snapshot) ---
    { id: "seed-21", type: "income", amount: 187400, category: "Salary", merchant: "Employer payroll", date: "2026-10-16", description: "Salary" },
    { id: "seed-22", type: "expense", amount: 45000, category: "Housing", merchant: "Home Rent", date: "2026-10-17" },
    { id: "seed-23", type: "expense", amount: 22000, category: "Food", merchant: "City Market", date: "2026-10-20" },
    { id: "seed-24", type: "expense", amount: 14000, category: "Transport", merchant: "Metro Pass", date: "2026-10-24" },

    // --- Previous period (17 Aug – 16 Sep) ---
    { id: "seed-9", type: "income", amount: 187400, category: "Salary", merchant: "Employer payroll", date: "2026-08-17" },
    { id: "seed-10", type: "expense", amount: 45000, category: "Housing", merchant: "Home Rent", date: "2026-08-18" },
    { id: "seed-11", type: "expense", amount: 23000, category: "Food", merchant: "City Market", date: "2026-08-22" },
    { id: "seed-12", type: "expense", amount: 14000, category: "Transport", merchant: "Metro Pass", date: "2026-08-26" },
    { id: "seed-13", type: "expense", amount: 12000, category: "Food", merchant: "Bakery", date: "2026-09-02" },
    { id: "seed-14", type: "expense", amount: 3990, category: "Lifestyle", merchant: "Streaming Plus", date: "2026-09-05" },

    // --- Two periods ago (17 Jul – 16 Aug) ---
    { id: "seed-15", type: "income", amount: 187400, category: "Salary", merchant: "Employer payroll", date: "2026-07-17" },
    { id: "seed-16", type: "expense", amount: 45000, category: "Housing", merchant: "Home Rent", date: "2026-07-18" },
    { id: "seed-17", type: "expense", amount: 21000, category: "Food", merchant: "City Market", date: "2026-07-23" },
    { id: "seed-18", type: "expense", amount: 16000, category: "Transport", merchant: "Metro Pass", date: "2026-07-28" },
    { id: "seed-19", type: "expense", amount: 8000, category: "Health", merchant: "Pharmacy", date: "2026-08-04" },
    { id: "seed-20", type: "expense", amount: 3990, category: "Lifestyle", merchant: "Streaming Plus", date: "2026-08-06" },
  ];

  return {
    version: DEMO_STATE_VERSION,
    transactions,
    salary: 187400,
    earned: 212800,
    available: 120000,
    reserveTarget: 60000,
    daysToPayday: 22,
    paydayDate,
  };
}

/**
 * Internal category IDs — stable keys used for storage and calculations.
 * Display labels are localized via `getCategoryLabel`.
 */
export const demoCategoryIds = [
  "Housing",
  "Food",
  "Transport",
  "Health",
  "Lifestyle",
  "Salary",
] as const;

/** Get the localized display label for a category ID. */
export function getCategoryLabel(categoryId: string, locale: Locale): string {
  const key = `category${categoryId.charAt(0).toUpperCase() + categoryId.slice(1)}` as keyof typeof locales.en.demo;
  return (locales[locale].demo[key] as string) ?? categoryId;
}

/** Categories offered by the demo editor, in a stable order (localized). */
export function getDemoCategories(locale: Locale): string[] {
  return demoCategoryIds.map((id) => getCategoryLabel(id, locale));
}

/* ------------------------------------------------------------------ *
 * Validation
 * ------------------------------------------------------------------ */

function isFiniteNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

/** Checks a parsed value has the shape this store promises. */
export function isValidDemoState(value: unknown): value is DemoState {
  if (!value || typeof value !== "object") return false;
  const state = value as Partial<DemoState>;
  if (typeof state.version !== "number") return false;
  if (!Array.isArray(state.transactions)) return false;
  for (const tx of state.transactions) {
    if (!tx || typeof tx !== "object") return false;
    if (typeof tx.id !== "string" || tx.id.length === 0) return false;
    if (tx.type !== "income" && tx.type !== "expense") return false;
    if (!isFiniteNumber(tx.amount) || tx.amount <= 0) return false;
    if (typeof tx.category !== "string" || tx.category.length === 0) return false;
    if (typeof tx.date !== "string" || !/^\d{4}-\d{2}-\d{2}$/.test(tx.date)) return false;
    if (tx.merchant !== undefined && typeof tx.merchant !== "string") return false;
    if (tx.description !== undefined && typeof tx.description !== "string") return false;
  }
  for (const field of ["available", "earned", "salary", "reserveTarget", "daysToPayday"] as const) {
    if (!isFiniteNumber(state[field])) return false;
  }
  return typeof state.paydayDate === "string";
}

/* ------------------------------------------------------------------ *
 * Storage
 * ------------------------------------------------------------------ */

export function loadDemoState(): DemoState {
  if (typeof window === "undefined") return createSeedDemoState();
  try {
    const raw = window.localStorage.getItem(demoStorageKey);
    if (!raw) return createSeedDemoState();
    const parsed: unknown = JSON.parse(raw);
    // Corrupt, truncated or unreadable state falls back to the seed rather than
    // rendering nonsense numbers.
    if (!isValidDemoState(parsed)) return createSeedDemoState();
    return parsed;
  } catch {
    return createSeedDemoState();
  }
}

export function saveDemoState(state: DemoState) {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(demoStorageKey, JSON.stringify(state));
  } catch {
    // Storage may be full or unavailable; the in-memory state still applies.
  }
}

export function resetDemoState(): DemoState {
  const seed = createSeedDemoState();
  saveDemoState(seed);
  return seed;
}

/* ------------------------------------------------------------------ *
 * React binding — every demo page reads the same namespaced demo state,
 * so edits made on one page are visible on the next page and after a
 * refresh. Nothing here touches the network.
 * ------------------------------------------------------------------ */

let cachedDemoState: DemoState | null = null;
const demoListeners = new Set<() => void>();

function readDemoState(): DemoState {
  if (cachedDemoState === null) cachedDemoState = loadDemoState();
  return cachedDemoState;
}

function notifyDemoState(): void {
  for (const listener of demoListeners) listener();
}

function onDemoStorageChanged(): void {
  cachedDemoState = loadDemoState();
  notifyDemoState();
}

function subscribeDemoState(listener: () => void): () => void {
  demoListeners.add(listener);
  if (typeof window !== "undefined") {
    window.addEventListener("storage", onDemoStorageChanged);
  }
  return () => {
    demoListeners.delete(listener);
    if (typeof window !== "undefined") {
      window.removeEventListener("storage", onDemoStorageChanged);
    }
  };
}

/** Read the namespaced demo state as a React external store. */
export function useDemoState(): DemoState {
  return useSyncExternalStore(subscribeDemoState, readDemoState, readDemoState);
}

/** Persist a new demo state locally and notify every demo subscriber. */
export function commitDemoState(next: DemoState): void {
  cachedDemoState = next;
  saveDemoState(next);
  notifyDemoState();
}

/* ------------------------------------------------------------------ *
 * Derived figures — all computed from the state, never hardcoded
 * ------------------------------------------------------------------ */

export interface DemoTotals {
  income: number;
  expense: number;
  net: number;
  transactionCount: number;
}

export function computeDemoTotals(state: DemoState): DemoTotals {
  let income = 0;
  let expense = 0;
  for (const tx of state.transactions) {
    if (tx.type === "income") income += tx.amount;
    else expense += tx.amount;
  }
  return {
    income,
    expense,
    net: income - expense,
    transactionCount: state.transactions.length,
  };
}

/**
 * Compute totals for the current pay period only.
 * The current period runs from paydayDate (inclusive) to the next payday (exclusive).
 * Since paydayDate is the first day of the period, we include transactions on or after paydayDate.
 */
export interface CurrentPeriodTotals {
  income: number;
  expense: number;
  net: number;
}

export function computeCurrentPeriodTotals(state: DemoState): CurrentPeriodTotals {
  const periodStart = state.paydayDate; // e.g., "2026-09-16"
  let income = 0;
  let expense = 0;
  for (const tx of state.transactions) {
    if (tx.date >= periodStart) {
      if (tx.type === "income") income += tx.amount;
      else expense += tx.amount;
    }
  }
  return {
    income,
    expense,
    net: income - expense,
  };
}

export interface CategoryTotal {
  category: string;
  amount: number;
  /** Share of total expenses, 0–1. */
  share: number;
}

export function computeDemoCategories(state: DemoState): CategoryTotal[] {
  const totals = new Map<string, number>();
  let expenseTotal = 0;
  for (const tx of state.transactions) {
    if (tx.type !== "expense") continue;
    expenseTotal += tx.amount;
    totals.set(tx.category, (totals.get(tx.category) ?? 0) + tx.amount);
  }
  return Array.from(totals.entries())
    .map(([category, amount]) => ({
      category,
      amount,
      share: expenseTotal > 0 ? amount / expenseTotal : 0,
    }))
    .sort((a, b) => b.amount - a.amount);
}

/**
 * Compute expense categories for the current pay period only.
 */
export function computeCurrentPeriodCategories(state: DemoState): CategoryTotal[] {
  const periodStart = state.paydayDate;
  const totals = new Map<string, number>();
  let expenseTotal = 0;
  for (const tx of state.transactions) {
    if (tx.type !== "expense") continue;
    if (tx.date < periodStart) continue;
    expenseTotal += tx.amount;
    totals.set(tx.category, (totals.get(tx.category) ?? 0) + tx.amount);
  }
  return Array.from(totals.entries())
    .map(([category, amount]) => ({
      category,
      amount,
      share: expenseTotal > 0 ? amount / expenseTotal : 0,
    }))
    .sort((a, b) => b.amount - a.amount);
}

export interface DemoSavings {
  /** Money set aside this period from the demo transactions. */
  saved: number;
  target: number;
  /** 0–1, capped at 1 so the bar stays meaningful. */
  progress: number;
  remaining: number;
}

export function computeDemoSavings(state: DemoState): DemoSavings {
  const currentPeriodExpense = computeCurrentPeriodTotals(state).expense;
  // Anything earned but not spent in the current period is treated as saved.
  const saved = Math.max(0, state.earned - currentPeriodExpense);
  const remaining = Math.max(0, state.reserveTarget - saved);
  return {
    saved,
    target: state.reserveTarget,
    progress: state.reserveTarget > 0 ? Math.min(1, saved / state.reserveTarget) : 0,
    remaining,
  };
}

export interface DemoMonthSummary {
  /** ISO month key, YYYY-MM. */
  key: string;
  label: string;
  income: number;
  expense: number;
}

export function computeDemoMonths(state: DemoState, locale: Locale): DemoMonthSummary[] {
  const byMonth = new Map<string, { income: number; expense: number }>();
  for (const tx of state.transactions) {
    const key = tx.date.slice(0, 7);
    const bucket = byMonth.get(key) ?? { income: 0, expense: 0 };
    if (tx.type === "income") bucket.income += tx.amount;
    else bucket.expense += tx.amount;
    byMonth.set(key, bucket);
  }
  return Array.from(byMonth.entries())
    .sort((a, b) => (a[0] < b[0] ? -1 : 1))
    .map(([key, values]) => ({
      key,
      label: monthLabel(key, locale),
      income: values.income,
      expense: values.expense,
    }));
}

const MONTH_NAMES_EN = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
const MONTH_NAMES_RU = ["январь", "февраль", "март", "апрель", "май", "июнь", "июль", "август", "сентябрь", "октябрь", "ноябрь", "декабрь"];

/** Full month name + year, capitalized for display. Locale is required. */
function monthLabel(key: string, locale: Locale): string {
  const [year, month] = key.split("-").map(Number);
  const names = locale === "ru" ? MONTH_NAMES_RU : MONTH_NAMES_EN;
  const name = names[month - 1] ?? key;
  const capitalized = name.length > 0 ? `${name[0].toLocaleUpperCase()}${name.slice(1)}` : name;
  return `${capitalized} ${year}`;
}

/* ------------------------------------------------------------------ *
 * Scenario analysis — mirrors the real what-if questions without
 * pretending to be a payroll decision.
 * ------------------------------------------------------------------ */

export type DemoScenarioStatus = "comfortable" | "caution" | "high-risk";

export interface DemoScenario {
  amount: number;
  availableAfter: number;
  /** Available balance once upcoming committed costs are met. */
  bufferAfter: number;
  status: DemoScenarioStatus;
  /** How much of earned wages this represents, 0–1. */
  shareOfEarned: number;
}

const UPCOMING_BILLS: DemoBill[] = [
  { id: "rent", label: "", amount: 45000, dueDate: "2026-11-01", isPaid: false },
  { id: "utilities", label: "", amount: 9000, dueDate: "2026-11-05", isPaid: false },
  { id: "phone", label: "", amount: 3400, dueDate: "2026-11-07", isPaid: false },
];

/** Get localized upcoming bills. */
export function upcomingBills(locale: Locale): DemoBill[] {
  return UPCOMING_BILLS.map((bill) => ({
    ...bill,
    label: locales[locale].demo[`bill${bill.id.charAt(0).toUpperCase() + bill.id.slice(1)}` as keyof typeof locales.en.demo] as string,
  }));
}

export function computeUpcomingTotal(): number {
  return UPCOMING_BILLS.reduce((sum, bill) => sum + bill.amount, 0);
}

export function computeUpcomingUnpaidTotal(): number {
  return UPCOMING_BILLS.filter((bill) => !bill.isPaid).reduce((sum, bill) => sum + bill.amount, 0);
}

export function evaluateDemoScenario(state: DemoState, amount: number): DemoScenario {
  const upcomingUnpaidTotal = computeUpcomingUnpaidTotal();
  const availableAfter = Math.max(0, state.available - amount);
  const bufferAfter = availableAfter - upcomingUnpaidTotal;

  let status: DemoScenarioStatus;
  if (bufferAfter >= state.reserveTarget) status = "comfortable";
  else if (bufferAfter >= 0) status = "caution";
  else status = "high-risk";

  return {
    amount,
    availableAfter,
    bufferAfter,
    status,
    shareOfEarned: state.earned > 0 ? Math.min(1, amount / state.earned) : 0,
  };
}

/** Largest requestable amount that still keeps the reserve intact. */
export function demoRecommendedAmount(state: DemoState): number {
  const upcomingUnpaidTotal = computeUpcomingUnpaidTotal();
  // Return the exact comfortable maximum: available - unpaid bills - reserve target.
  // This is the same formula used by computeDemoPlan and evaluateDemoScenario.
  return Math.max(0, state.available - upcomingUnpaidTotal - state.reserveTarget);
}

/** Plan for the current pay period, derived from the state. */
export interface DemoPlanLine {
  label: string;
  amount: number;
}

export function computeDemoPlan(state: DemoState, locale: Locale): DemoPlanLine[] {
  const recommended = demoRecommendedAmount(state);
  const upcomingTotal = computeUpcomingTotal();
  const upcomingUnpaidTotal = computeUpcomingUnpaidTotal();
  const savings = computeDemoSavings(state);
  return [
    { label: locales[locale].demo.planUpcomingBills, amount: upcomingTotal },
    { label: locales[locale].demo.planReserveTarget, amount: state.reserveTarget },
    { label: locales[locale].demo.planComfortableWithdrawal, amount: Math.max(0, state.available - upcomingUnpaidTotal - state.reserveTarget) },
    { label: locales[locale].demo.planSuggestedAccessAmount, amount: recommended },
  ];
}

/* ------------------------------------------------------------------ *
 * Transactions mutations
 * ------------------------------------------------------------------ */

function nextId(transactions: DemoTransaction[]): string {
  let max = 0;
  for (const tx of transactions) {
    const match = /^demo-(\d+)$/.exec(tx.id);
    if (match) max = Math.max(max, Number(match[1]));
  }
  return `demo-${max + 1}`;
}

export function addDemoTransaction(
  state: DemoState,
  input: Omit<DemoTransaction, "id">,
): { state: DemoState; transaction: DemoTransaction } {
  const transaction: DemoTransaction = { ...input, id: nextId(state.transactions) };
  return {
    state: { ...state, transactions: [...state.transactions, transaction] },
    transaction,
  };
}

export function editDemoTransaction(
  state: DemoState,
  id: string,
  changes: Partial<Omit<DemoTransaction, "id">>,
): DemoState {
  let replaced = false;
  const transactions = state.transactions.map((tx) => {
    if (tx.id !== id) return tx;
    replaced = true;
    return { ...tx, ...changes, id: tx.id };
  });
  // Unknown ids leave the state untouched rather than appending a duplicate.
  return replaced ? { ...state, transactions } : state;
}

export function deleteDemoTransaction(state: DemoState, id: string): DemoState {
  return {
    ...state,
    transactions: state.transactions.filter((tx) => tx.id !== id),
  };
}

export function formatDemoAmount(amount: number, locale: "en" | "ru" = "ru"): string {
  return formatMajorAsTenge(amount, locale);
}

/* ------------------------------------------------------------------ *
 * Demo identity
 *
 * The public demo is shown inside the same application shell as the
 * authenticated dashboard. Both the demo layout and the demo overview read the
 * identity from here, so the name shown is always the same fictional one and
 * never derived from a real account.
 * ------------------------------------------------------------------ */

/** Fictional account used only by the public demo shell. */
export const demoUserEmail = "demo@arqau.kz";

/** Display name of the fictional demo employee, in the active language. */
export function demoUserName(locale: Locale = "ru"): string {
  return locale === "ru" ? "Демо сотрудник" : "Demo Employee";
}
