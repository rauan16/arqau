// Single source of truth for ARQAU's demo scenario.
// All figures on the landing page are fictional demo data used to
// illustrate the product concept — not real customer information.

export const scenario = {
  employeeName: "Guest",
  month: "September 2026",
  salary: 300000,
  earned: 187400,
  alreadyReceived: 67400,
  available: 120000,
  upcomingExpensesTotal: 85000,
  reserveTarget: 60000,
  recommended: 50000,
  nextPaydayDays: 9,
  currency: "₸",
  illustrativeExample: true,
};

/** 0-based month index matching `scenario.month` (September 2026). */
export const demoCurrentMonthIndex = 8;

export const upcomingExpenses = [
  { label: "Rent", amount: 45000 },
  { label: "Food", amount: 25000 },
  { label: "Transport", amount: 15000 },
];

export const weeklyEarnings = [22000, 26000, 24000, 30000, 28000, 33000, 24400];

/* ------------------------------------------------------------------ *
 * Product demo: analytics
 *
 * The landing page plots illustrative datasets for every metric/period
 * combination. Values are generated deterministically from a seeded
 * profile so a given metric + period always renders the same chart.
 * ------------------------------------------------------------------ */

export type AnalyticsMetricId = "expenses" | "income" | "savings";

export type AnalyticsPeriodId = "7d" | "30d" | "3m" | "6m" | "12m";

export type AnalyticsGranularity = "day" | "month";

export type AnalyticsPoint = {
  label: string;
  value: number;
};

export type AnalyticsPeriod = {
  id: AnalyticsPeriodId;
  /** Number of plotted points. */
  points: number;
  /** Aggregate size of a single plotted point. */
  granularity: AnalyticsGranularity;
};

export const analyticsPeriods: readonly AnalyticsPeriod[] = [
  { id: "7d", points: 7, granularity: "day" },
  { id: "30d", points: 30, granularity: "day" },
  { id: "3m", points: 3, granularity: "month" },
  { id: "6m", points: 6, granularity: "month" },
  { id: "12m", points: 12, granularity: "month" },
];

export const defaultAnalyticsPeriod: AnalyticsPeriodId = "6m";

export const defaultAnalyticsMetric: AnalyticsMetricId = "expenses";

type MetricProfile = {
  id: AnalyticsMetricId;
  /** Typical monthly total for the metric. */
  monthlyBase: number;
  /** Weekday weighting used for daily views (7 entries, Mon → Sun). */
  dailyPattern: number[];
  /** Relative drift applied per plotted month. */
  monthlyTrend: number;
  monthlySwing: number;
  dailySwing: number;
  seed: number;
};

export const analyticsMetrics: readonly MetricProfile[] = [
  {
    id: "expenses",
    monthlyBase: 96000,
    dailyPattern: [1.02, 0.98, 1.05, 1.12, 1.24, 1.18, 0.86],
    monthlyTrend: 0.018,
    monthlySwing: 0.16,
    dailySwing: 0.18,
    seed: 17,
  },
  {
    id: "income",
    monthlyBase: 300000,
    dailyPattern: [1, 1, 1, 1, 1, 0.16, 0.16],
    monthlyTrend: 0.01,
    monthlySwing: 0.05,
    dailySwing: 0.08,
    seed: 43,
  },
  {
    id: "savings",
    monthlyBase: 42000,
    dailyPattern: [0.9, 1.1, 1, 1.15, 0.95, 1.3, 1.2],
    monthlyTrend: 0.06,
    monthlySwing: 0.26,
    dailySwing: 0.22,
    seed: 71,
  },
];

export function getAnalyticsPeriod(id: AnalyticsPeriodId): AnalyticsPeriod {
  const found = analyticsPeriods.find((p) => p.id === id);
  if (!found) throw new Error(`Unknown analytics period: ${id}`);
  return found;
}

export function getMetricProfile(id: AnalyticsMetricId): MetricProfile {
  const found = analyticsMetrics.find((m) => m.id === id);
  if (!found) throw new Error(`Unknown analytics metric: ${id}`);
  return found;
}

// Deterministic pseudo-random source in [0, 1) — keeps demo charts stable
// across renders, reloads and test runs without external dependencies.
function noise01(seed: number, index: number): number {
  const raw = Math.sin(seed * 12.9898 + index * 78.233) * 43758.5453;
  return raw - Math.floor(raw);
}

function roundTo(value: number, step: number): number {
  return Math.round(value / step) * step;
}

function monthlyValue(profile: MetricProfile, index: number): number {
  const trend = 1 + profile.monthlyTrend * index;
  const swing = 1 + (noise01(profile.seed, index) * 2 - 1) * profile.monthlySwing;
  return Math.max(1000, roundTo(profile.monthlyBase * trend * swing, 1000));
}

function dailyValue(profile: MetricProfile, index: number): number {
  const pattern = profile.dailyPattern[index % profile.dailyPattern.length];
  const drift = 1 + profile.monthlyTrend * 0.02 * index;
  const swing = 1 + (noise01(profile.seed + 3, index) * 2 - 1) * profile.dailySwing;
  // Salary lands mid-cycle, which keeps daily income views believable.
  const payday = profile.id === "income" && (index + 1) % 15 === 0 ? 2.4 : 1;
  const value = (profile.monthlyBase / 30) * pattern * drift * swing * payday;
  return Math.max(100, roundTo(value, 100));
}

export type AnalyticsLabels = {
  /** 7 short weekday names, Monday first. */
  weekdays: string[];
  /** 12 short month names, January first. */
  months: string[];
  /** Index of the demo "current" month inside `months` (0-based). */
  currentMonthIndex: number;
};

export type AnalyticsSummary = {
  metric: AnalyticsMetricId;
  period: AnalyticsPeriodId;
  granularity: AnalyticsGranularity;
  points: AnalyticsPoint[];
  pointCount: number;
  total: number;
  average: number;
  peak: AnalyticsPoint;
  lowest: AnalyticsPoint;
};

/**
 * Builds the chart + summary for one metric/period pair.
 * Labels come from the active locale so the axis always matches the range.
 */
export function buildAnalytics(
  metric: AnalyticsMetricId,
  period: AnalyticsPeriodId,
  labels: AnalyticsLabels,
): AnalyticsSummary {
  const profile = getMetricProfile(metric);
  const config = getAnalyticsPeriod(period);

  const points: AnalyticsPoint[] = [];
  for (let i = 0; i < config.points; i += 1) {
    const value =
      config.granularity === "month"
        ? monthlyValue(profile, i)
        : dailyValue(profile, i);

    const label =
      config.granularity === "month"
        ? labels.months[(labels.currentMonthIndex - config.points + 1 + i + 12) % 12]
        : config.points === 7
          ? labels.weekdays[i % 7]
          : String(i + 1);

    points.push({ label, value });
  }

  const values = points.map((p) => p.value);
  const total = values.reduce((sum, v) => sum + v, 0);
  const peak = points.reduce((best, p) => (p.value > best.value ? p : best), points[0]);
  const lowest = points.reduce((best, p) => (p.value < best.value ? p : best), points[0]);

  return {
    metric,
    period,
    granularity: config.granularity,
    points,
    pointCount: config.points,
    total,
    average: Math.round(total / config.points),
    peak,
    lowest,
  };
}

/** How many bars share a visible axis label, so 30-point charts stay readable. */
export function getLabelStride(pointCount: number): number {
  if (pointCount <= 7) return 1;
  if (pointCount <= 12) return 2;
  return 5;
}

export function shouldShowLabel(index: number, pointCount: number): boolean {
  const stride = getLabelStride(pointCount);
  return index % stride === 0 || index === pointCount - 1;
}

// Deterministic status logic for the what-if simulator.
// Every screen that shows a withdrawal amount reads from this function
// so the UI never drifts into contradictory numbers.
export type WithdrawalStatus = "comfortable" | "caution" | "high-risk";

export function evaluateWithdrawal(amount: number) {
  const remainingAvailable = scenario.available - amount;
  const reserveAfter = remainingAvailable;
  const coversExpenses = remainingAvailable >= scenario.upcomingExpensesTotal;
  const meetsReserve = reserveAfter >= scenario.reserveTarget;

  let status: WithdrawalStatus;
  if (meetsReserve) status = "comfortable";
  else if (coversExpenses) status = "caution";
  else status = "high-risk";

  const statusCopy: Record<WithdrawalStatus, { label: string; note: string }> = {
    comfortable: {
      label: "Comfortable",
      note: "Your upcoming expenses stay covered and your reserve holds steady.",
    },
    caution: {
      label: "Caution",
      note: "Your reserve would fall below the recommended level.",
    },
    "high-risk": {
      label: "High risk",
      note: "This would leave your upcoming expenses uncovered.",
    },
  };

  return {
    amount,
    remainingAvailable,
    reserveAfter,
    status,
    ...statusCopy[status],
  };
}

/* ------------------------------------------------------------------ *
 * Product demo: withdrawal amounts
 * ------------------------------------------------------------------ */

/** Selectable demo amounts, in tenge. */
export const withdrawalPresets: readonly number[] = [10000, 30000, 50000, 100000];

/** A preset can only be chosen while it fits inside the available balance. */
export function isPresetAvailable(amount: number, available: number = scenario.available): boolean {
  return amount > 0 && amount <= available;
}

export function getAvailablePresets(available: number = scenario.available): number[] {
  return withdrawalPresets.filter((amount) => isPresetAvailable(amount, available));
}

/**
 * Largest preset that keeps the reserve intact. Used as the default
 * selection and as the "recommended amount" surfaced in the demo cards.
 */
export function getRecommendedWithdrawal(): number {
  const available = scenario.available;
  const affordable = withdrawalPresets.filter((amount) => isPresetAvailable(amount, available));
  const comfortable = affordable.filter((amount) => evaluateWithdrawal(amount).status === "comfortable");
  const pool = comfortable.length > 0 ? comfortable : affordable;
  return Math.max(...pool);
}

export type WithdrawalGuidance = {
  amount: number;
  remainingAvailable: number;
  status: WithdrawalStatus;
};

/** Status of a chosen amount — drives the advice copy in the demo. */
export function getWithdrawalGuidance(amount: number): WithdrawalGuidance {
  const result = evaluateWithdrawal(amount);
  return {
    amount,
    remainingAvailable: result.remainingAvailable,
    status: result.status,
  };
}

export const employerDemo = {
  employees: 1284,
  earnedPayroll: 38400000,
  activeThisMonth: 742,
  withdrawals: 12800000,
  weeklyActivity: [4.1, 5.6, 4.9, 6.8, 7.2, 6.1, 8.4],
  illustrativeExample: true,
};

export type Transaction = {
  id: string;
  merchant: string;
  category: string;
  amount: number;
  date: string;
  status: "Completed" | "Pending";
};

export const transactions: Transaction[] = [
  { id: "tx-1", merchant: "City Market", category: "Food", amount: 12400, date: "Sep 06, 2026", status: "Completed" },
  { id: "tx-2", merchant: "Metro Pass", category: "Transport", amount: 4200, date: "Sep 05, 2026", status: "Completed" },
  { id: "tx-3", merchant: "Home Rent", category: "Housing", amount: 45000, date: "Sep 01, 2026", status: "Completed" },
  { id: "tx-4", merchant: "Streaming Plus", category: "Lifestyle", amount: 3990, date: "Aug 29, 2026", status: "Pending" },
];

export const moneyOpportunities = [
  { title: "Access earned wages", description: "Take a controlled amount from income you have already earned.", amount: scenario.recommended, difficulty: "Immediate", time: "Today" },
  { title: "Review upcoming expenses", description: "Plan your next payments and keep your reserve intact.", amount: 0, difficulty: "Easy", time: "5 min" },
  { title: "Build your reserve", description: "Set aside a little more this month for a stronger safety net.", amount: scenario.reserveTarget, difficulty: "Steady", time: "Monthly" },
];

export const aiInsights = [
  "Example: upcoming expenses can be compared with an access amount.",
  "Example: spending categories can be surfaced once real activity is connected.",
  "Example: a pay-cycle view can help frame a responsible access decision.",
];

export function formatTenge(value: number) {
  return `${value.toLocaleString("ru-RU")} ₸`;
}
