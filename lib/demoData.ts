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

export const upcomingExpenses = [
  { label: "Rent", amount: 45000 },
  { label: "Food", amount: 25000 },
  { label: "Transport", amount: 15000 },
];

export const weeklyEarnings = [22000, 26000, 24000, 30000, 28000, 33000, 24400];

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
  return `${value.toLocaleString("en-US")} ₸`;
}
