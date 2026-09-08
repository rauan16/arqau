export type EarningsRecord = {
  id: string;
  amount: number;
  date: string;
  source: string;
  note?: string;
};

export type ExpenseRecord = {
  id: string;
  amount: number;
  category: string;
  date: string;
  note?: string;
};

export type TransactionRecord = {
  id: string;
  merchant: string;
  category: string;
  amount: number;
  date: string;
  status: "Completed" | "Pending";
};

export type UserFinancialData = {
  earnings: EarningsRecord[];
  expenses: ExpenseRecord[];
  transactions: TransactionRecord[];
};

export type UserProfile = {
  name: string;
  payFrequency: string;
  monthlyIncomeRange: string;
  paydayRange: string;
  financialPressure: string;
  earlyAccessUseCase: string;
  aiHelpPreference: string;
};

export const profileStorageKey = "arqau-user-profile";
export const financialDataStorageKey = "arqau-financial-data";

export function loadProfile(): UserProfile | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(profileStorageKey);
    if (!raw) return null;
    return JSON.parse(raw) as UserProfile;
  } catch {
    return null;
  }
}

export function saveProfile(profile: UserProfile) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(profileStorageKey, JSON.stringify(profile));
}

export function loadFinancialData(): UserFinancialData {
  if (typeof window === "undefined") return { earnings: [], expenses: [], transactions: [] };
  try {
    const raw = window.localStorage.getItem(financialDataStorageKey);
    if (!raw) return { earnings: [], expenses: [], transactions: [] };
    return JSON.parse(raw) as UserFinancialData;
  } catch {
    return { earnings: [], expenses: [], transactions: [] };
  }
}

export function saveFinancialData(data: UserFinancialData) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(financialDataStorageKey, JSON.stringify(data));
}

export function addEarning(record: Omit<EarningsRecord, "id">) {
  const data = loadFinancialData();
  data.earnings.push({
    ...record,
    id: `earn-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`,
  });
  saveFinancialData(data);
  return data;
}

export function addExpense(record: Omit<ExpenseRecord, "id">) {
  const data = loadFinancialData();
  data.expenses.push({
    ...record,
    id: `exp-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`,
  });
  saveFinancialData(data);
  return data;
}

export function addTransaction(record: Omit<TransactionRecord, "id">) {
  const data = loadFinancialData();
  data.transactions.push({
    ...record,
    id: `tx-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`,
  });
  saveFinancialData(data);
  return data;
}
