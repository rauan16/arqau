const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface User {
  id: string;
  email: string;
  name?: string;
  is_verified: boolean;
  is_active: boolean;
  created_at: string;
}

export interface OnboardingData {
  pay_frequency?: string;
  monthly_income_range?: string;
  payday_range?: string;
  financial_pressure?: string;
  early_access_use_case?: string;
  ai_help_preference?: string;
}

export interface Transaction {
  id: string;
  user_id: string;
  type: "income" | "expense";
  amount_minor: number;
  category?: string;
  merchant?: string;
  description?: string;
  date?: string;
  created_at?: string;
}

export interface FinanceSummary {
  total_income_minor: number;
  total_expense_minor: number;
  net_balance_minor: number;
  transaction_count: number;
}

export interface EarnedWages {
  id: string;
  user_id: string;
  earned_amount_minor: number;
  accessed_amount_minor: number;
  available_amount_minor: number;
  period_start?: string;
  period_end?: string;
}

export interface WageAccessRequest {
  id: string;
  user_id: string;
  amount_minor: number;
  status: "pending" | "approved" | "rejected" | "completed";
  reason?: string;
  created_at: string;
}

export interface Budget {
  id: string;
  user_id: string;
  category: string;
  limit_minor: number;
  spent_minor: number;
  period: string;
  remaining_minor: number;
}

export interface Goal {
  id: string;
  user_id: string;
  title: string;
  target_minor: number;
  current_minor: number;
  deadline?: string;
  status: string;
  progress_pct: number;
}

export interface WithdrawalAnalysis {
  withdrawal_amount: number;
  remaining_amount: number;
  available_amount: number;
  earned_amount: number;
  accessed_amount: number;
  total_income: number;
  total_expenses: number;
  net_balance: number;
  covered_expenses: boolean;
  reserve_status: string;
  risk_level: string;
  recommendation: string;
  explanation: string;
  disclaimer: string;
}

class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem("arqau_token");
}

function setToken(token: string) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem("arqau_token", token);
}

function clearToken() {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem("arqau_token");
}

async function request<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string> || {}),
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    if (response.status === 401) {
      clearToken();
      if (typeof window !== "undefined") {
        window.location.href = "/login";
      }
    }
    const body = await response.json().catch(() => ({}));
    const detail = body?.detail || body?.message || `HTTP ${response.status}`;
    throw new ApiError(detail, response.status);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json();
}

export const api = {
  auth: {
    register: (email: string, password: string, name?: string) =>
      request<{ access_token: string; token_type: string; user_id: string }>("/auth/register", {
        method: "POST",
        body: JSON.stringify({ email, password, name }),
      }),
    login: (email: string, password: string) =>
      request<{ access_token: string; token_type: string; user_id: string }>("/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      }),
    me: () => request<User>("/auth/me"),
  },

  onboarding: {
    save: (data: OnboardingData) =>
      request("/auth/onboarding", {
        method: "PUT",
        body: JSON.stringify(data),
      }),
    get: () => request<OnboardingData>("/auth/onboarding"),
    isComplete: () => request<{ complete: boolean }>("/auth/onboarding"),
  },

  finance: {
    getSummary: () => request<FinanceSummary>("/finance/summary"),
    getTransactions: (limit = 100, offset = 0) =>
      request<Transaction[]>(`/transactions?limit=${limit}&offset=${offset}`),
    createTransaction: (data: { type: string; amount_minor: number; category?: string; merchant?: string; description?: string }) =>
      request<Transaction>("/transactions", {
        method: "POST",
        body: JSON.stringify(data),
      }),
    updateTransaction: (id: string, data: Partial<Transaction>) =>
      request<Transaction>(`/transactions/${id}`, {
        method: "PUT",
        body: JSON.stringify(data),
      }),
    deleteTransaction: (id: string) =>
      request<void>(`/transactions/${id}`, { method: "DELETE" }),
    getBudgets: () => request<Budget[]>("/budgets"),
    createBudget: (data: { category: string; limit_minor: number; period?: string }) =>
      request<Budget>("/budgets", { method: "POST", body: JSON.stringify(data) }),
    updateBudget: (id: string, data: Partial<Budget>) =>
      request<Budget>(`/budgets/${id}`, { method: "PUT", body: JSON.stringify(data) }),
    deleteBudget: (id: string) =>
      request<void>(`/budgets/${id}`, { method: "DELETE" }),
    getGoals: () => request<Goal[]>("/goals"),
    createGoal: (data: { title: string; target_minor: number; current_minor?: number; deadline?: string }) =>
      request<Goal>("/goals", { method: "POST", body: JSON.stringify(data) }),
    updateGoal: (id: string, data: Partial<Goal>) =>
      request<Goal>(`/goals/${id}`, { method: "PUT", body: JSON.stringify(data) }),
    deleteGoal: (id: string) =>
      request<void>(`/goals/${id}`, { method: "DELETE" }),
  },

  ewa: {
    getEarned: () => request<EarnedWages>("/ewa/earned"),
    updateEarned: (data: { earned_amount_minor: number }) =>
      request<EarnedWages>("/ewa/earned", { method: "PUT", body: JSON.stringify(data) }),
    getAvailable: () => request<{ available_amount_minor: number }>("/ewa/available"),
    createRequest: (data: { amount_minor: number; reason?: string }) =>
      request<WageAccessRequest>("/ewa/request", { method: "POST", body: JSON.stringify(data) }),
    getRequests: () => request<WageAccessRequest[]>("/ewa/requests"),
  },

  ai: {
    analyzeWithdrawal: (withdrawal_amount: number) =>
      request<WithdrawalAnalysis>("/ai/analyze-withdrawal", {
        method: "POST",
        body: JSON.stringify({ withdrawal_amount }),
      }),
    chat: (message: string, conversation_id?: string) =>
      request<{ response: string; disclaimer: string }>("/ai/chat", {
        method: "POST",
        body: JSON.stringify({ message, conversation_id }),
      }),
  },
};

export { getToken, setToken, clearToken, ApiError };
