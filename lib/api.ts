import { toReadableError } from "./errorMessages";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const BFF_BASE = "/api";

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

export interface EmployerCreate {
  legal_name: string;
  display_name?: string;
  registration_number?: string;
  country?: string;
}

export interface EmployerRead {
  id: string;
  legal_name: string;
  display_name?: string | null;
  registration_number?: string | null;
  country?: string | null;
  status: string;
  created_at: string;
  updated_at?: string | null;
}

export interface EmployeeRead {
  id: string;
  user_id: string;
  external_employee_id?: string | null;
  display_name?: string | null;
  status: string;
  created_at: string;
  updated_at?: string | null;
}

export interface EmploymentRead {
  id: string;
  employee_id: string;
  employer_id: string;
  employment_type?: string | null;
  status: string;
  start_date?: string | null;
  end_date?: string | null;
  eligible_from?: string | null;
  eligible_to?: string | null;
  created_at: string;
  updated_at?: string | null;
}

export interface SalaryProfileRead {
  id: string;
  employment_id: string;
  currency: string;
  monthly_salary_amount_minor: number;
  pay_schedule: string;
  payday_day?: number | null;
  effective_from: string;
  effective_to?: string | null;
  status: string;
  source: string;
  created_at: string;
  updated_at?: string | null;
}

export interface EwaPolicyRead {
  id: string;
  employer_id: string;
  enabled: boolean;
  max_access_percentage: number;
  max_withdrawals_per_period?: number | null;
  minimum_tenure_days?: number | null;
  minimum_remaining_salary_minor?: number | null;
  minimum_withdrawal_minor?: number | null;
  maximum_withdrawal_minor?: number | null;
  created_at: string;
  updated_at?: string | null;
}

export type WageAccessRequestStatus =
  | "pending"
  | "approved"
  | "paid"
  | "rejected"
  | "cancelled"
  // Legacy rows may still carry "completed"; the backend lifecycle uses
  // pending → approved → paid (plus rejected / cancelled).
  | "completed";

/**
 * Shape of `GET /ewa/requests` (backend `schemas.ewa.WageAccessRequestResponse`).
 * Field-for-field match, including the lifecycle timestamps and the optional
 * pay-period binding, so the History page can report real statuses and dates.
 */
export interface WageAccessRequest {
  id: string;
  user_id: string;
  amount_minor: number;
  status: WageAccessRequestStatus;
  reason?: string | null;
  pay_period_start?: string | null;
  pay_period_end?: string | null;
  approved_at?: string | null;
  rejected_at?: string | null;
  cancelled_at?: string | null;
  paid_at?: string | null;
  rejection_reason?: string | null;
  created_at: string;
  updated_at?: string | null;
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

export interface FinancialContextEmployment {
  employment_id?: string | null;
  employer_id?: string | null;
  employer_name?: string | null;
  employment_status?: string | null;
}

export interface FinancialContextIncome {
  salary_amount_minor?: number | null;
  currency?: string | null;
  pay_period_start?: string | null;
  pay_period_end?: string | null;
}

export interface FinancialContextEwa {
  earned_amount_minor: number;
  policy_limit_minor: number;
  reserved_amount_minor: number;
  paid_amount_minor: number;
  available_amount_minor: number;
  max_requestable_amount_minor: number;
  pay_period_start?: string | null;
  pay_period_end?: string | null;
  calculation_date?: string | null;
  salary_amount_minor?: number | null;
  eligible: boolean;
  eligibility_reasons: string[];
  minimum_withdrawal_minor?: number | null;
  maximum_withdrawal_minor?: number | null;
  can_request_withdrawal: boolean;
  max_withdrawals_per_period?: number | null;
  withdrawals_this_period: number;
}

export interface FinancialContextRecentWithdrawal {
  id: string;
  amount_minor: number;
  status: string;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface FinancialContextWithdrawalHistory {
  available: boolean;
  total_requests: number;
  pending_count: number;
  approved_count: number;
  paid_count: number;
  rejected_count: number;
  cancelled_count: number;
  requested_amount_minor: number;
  paid_amount_minor: number;
  recent_requests: FinancialContextRecentWithdrawal[];
}

export interface FinancialContextCategory {
  category: string;
  amount_minor: number;
  transaction_count: number;
}

export interface FinancialContextSpending {
  available: boolean;
  total_spending_minor?: number | null;
  transaction_count: number;
  essential_spending_minor?: number | null;
  discretionary_spending_minor?: number | null;
  category_breakdown: FinancialContextCategory[];
}

export interface FinancialContextBudget {
  available: boolean;
  total_budget_minor?: number | null;
  spent_minor?: number | null;
  remaining_minor?: number | null;
}

export interface FinancialContextGoal {
  id: string;
  title: string;
  target_minor: number;
  current_minor: number;
  status: string;
  progress_pct: number;
}

export interface FinancialContextGoals {
  available: boolean;
  active_goals_count?: number | null;
  total_target_minor?: number | null;
  total_saved_minor?: number | null;
  goals: FinancialContextGoal[];
}

export interface FinancialContextDataQuality {
  has_salary_profile: boolean;
  has_ewa_policy: boolean;
  has_transactions: boolean;
  has_budget: boolean;
  has_goals: boolean;
  missing_data: string[];
}

export interface FinancialContext {
  user_id: string;
  generated_at?: string | null;
  calculation_date?: string | null;
  employment: FinancialContextEmployment;
  income: FinancialContextIncome;
  ewa: FinancialContextEwa;
  withdrawal_history: FinancialContextWithdrawalHistory;
  spending: FinancialContextSpending;
  budget: FinancialContextBudget;
  goals: FinancialContextGoals;
  data_quality: FinancialContextDataQuality;
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

export interface EWAResultResponse {
  salary_amount_minor: number;
  earned_amount_minor: number;
  policy_limit_minor: number;
  reserved_amount_minor: number;
  paid_amount_minor: number;
  available_amount_minor: number;
  pay_period_start: string;
  pay_period_end: string;
  calculation_date: string;
  eligible: boolean;
  eligibility_reasons: string[];
  minimum_withdrawal_minor: number | null;
  maximum_withdrawal_minor: number | null;
  can_request_withdrawal: boolean;
  max_withdrawals_per_period: number | null;
  withdrawals_this_period: number;
  max_requestable_amount_minor: number;
}

/**
 * Employer-scoped listing (`GET /ewa/employers/{id}/requests`) returns the same
 * schema as the employee-facing `/ewa/requests`.
 */
export type WageAccessRequestRead = WageAccessRequest;

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

export interface WithdrawalDecisionResponse {
  requested_amount_minor: number;
  requestable: boolean;
  blocking_reasons: string[];
  current_available_amount_minor: number | null;
  max_requestable_amount_minor: number | null;
  snapshot_only: boolean;
  decision: StructuredDecision;
}

export interface DecisionFact {
  code: string;
  text: string;
}

export interface DecisionConsideration {
  code: string;
  text: string;
}

export interface DecisionOption {
  code: string;
  text: string;
}

export interface AIMetadata {
  generated: boolean;
  fallback_used: boolean;
  provider: string | null;
  model: string | null;
}

export interface StructuredDecision {
  summary: string;
  status_explanation: string;
  key_facts: DecisionFact[];
  considerations: DecisionConsideration[];
  options: DecisionOption[];
  data_limitations: string[];
  disclaimer: string;
  ai_metadata: AIMetadata;
}

/**
 * Authoritative, read-only withdrawal analysis (Phase 3.2).
 *
 * Field-for-field match of the backend `financial_context.WithdrawalAnalysis`
 * schema. There is deliberately NO risk level, recommendation, reserve status
 * or covered-expenses flag: those encoded an AI-side financial calculation the
 * backend architecture prohibits. Every value here is server-owned.
 */
export interface WithdrawalRequestability {
  requestable: boolean;
  blocking_reasons: string[];
  authoritative_eligibility_reasons: string[];
}

export interface WithdrawalCurrentState {
  salary_amount_minor?: number | null;
  earned_amount_minor?: number | null;
  policy_limit_minor?: number | null;
  reserved_amount_minor?: number | null;
  paid_amount_minor?: number | null;
  available_amount_minor?: number | null;
  max_requestable_amount_minor?: number | null;
}

export interface WithdrawalImpact {
  remaining_available_amount_minor?: number | null;
  remaining_max_requestable_amount_minor?: number | null;
  requested_share_of_earned_bps?: number | null;
  requested_share_of_policy_limit_bps?: number | null;
  exposure_before_minor?: number | null;
  exposure_after_minor?: number | null;
  exposure_share_of_earned_before_bps?: number | null;
  exposure_share_of_earned_after_bps?: number | null;
}

export interface WithdrawalFrequency {
  withdrawals_this_period: number;
  max_withdrawals_per_period?: number | null;
  remaining_slots_before?: number | null;
  remaining_slots_after?: number | null;
}

export interface WithdrawalBudgetImpact {
  available: boolean;
  total_budget_minor?: number | null;
  current_spent_minor?: number | null;
  current_remaining_minor?: number | null;
  withdrawal_share_of_budget_bps?: number | null;
}

export interface WithdrawalDataQuality {
  has_transactions: boolean;
  has_budget: boolean;
  has_goals: boolean;
  unavailable_analysis?: string | null;
}

export interface WithdrawalAnalysis {
  requested_amount_minor: number;
  requestability: WithdrawalRequestability;
  current_state: WithdrawalCurrentState;
  impact: WithdrawalImpact;
  withdrawal_frequency: WithdrawalFrequency;
  budget_impact: WithdrawalBudgetImpact;
  data_quality: WithdrawalDataQuality;
  snapshot_only: boolean;
}

export interface CopilotFact {
  code: string;
  text: string;
}

export interface CopilotMetadata {
  generated: boolean;
  fallback_used: boolean;
  provider: string | null;
  model: string | null;
  fallback_reason: string | null;
}

export interface SpendingCategoryFact {
  category: string;
  amount_minor: number;
  transaction_count: number;
}

export interface AuthoritativeCopilotFacts {
  calculation_date: string | null;
  pay_period_start: string | null;
  pay_period_end: string | null;
  salary_amount_minor: number | null;
  currency: string | null;
  earned_amount_minor: number | null;
  policy_limit_minor: number | null;
  reserved_amount_minor: number | null;
  paid_amount_minor: number | null;
  available_amount_minor: number | null;
  max_requestable_amount_minor: number | null;
  minimum_withdrawal_minor: number | null;
  maximum_withdrawal_minor: number | null;
  eligible: boolean | null;
  eligibility_reasons: string[];
  can_request_withdrawal: boolean | null;
  withdrawals_this_period: number | null;
  max_withdrawals_per_period: number | null;
  total_withdrawal_requests: number | null;
  pending_withdrawal_count: number | null;
  approved_withdrawal_count: number | null;
  paid_withdrawal_count: number | null;
  paid_withdrawal_amount_minor: number | null;
  spending_available: boolean | null;
  total_spending_minor: number | null;
  transaction_count: number | null;
  top_spending_categories: SpendingCategoryFact[];
  budget_available: boolean | null;
  budget_total_minor: number | null;
  budget_spent_minor: number | null;
  budget_remaining_minor: number | null;
  goals_available: boolean | null;
  active_goals_count: number | null;
  total_goal_target_minor: number | null;
  total_goal_saved_minor: number | null;
  has_salary_profile: boolean | null;
  has_ewa_policy: boolean | null;
  has_transactions: boolean | null;
  has_budget: boolean | null;
  has_goals: boolean | null;
  missing_data: string[];
  availability_note: string;
}

export interface CopilotResponse {
  response: string;
  key_facts: CopilotFact[];
  data_limitations: string[];
  suggested_questions: string[];
  disclaimer: string;
  authoritative_facts: AuthoritativeCopilotFacts;
  withdrawal_analysis: WithdrawalAnalysis | null;
  product_search_results: ProductSearchResultItem[] | null;
  conversation_id: string | null;
  conversation_persisted: boolean;
  ai_metadata: CopilotMetadata;
  read_only: boolean;
  snapshot_only: boolean;
}

export interface ProductSearchResultItem {
  source: string;
  product_id: string;
  title: string;
  price_minor: number;
  currency: string;
  seller: string | null;
  url: string | null;
  availability: string | null;
  delivery_info: string | null;
}

class ApiError extends Error {
  status: number;
  retryAfter: number | null;
  constructor(message: string, status: number, retryAfter: number | null = null) {
    super(message);
    this.status = status;
    this.retryAfter = retryAfter;
  }
}

function parseRetryAfter(header: string | null): number | null {
  if (!header) return null;
  const seconds = Number(header.trim());
  if (!Number.isNaN(seconds) && Number.isFinite(seconds)) {
    return Math.max(0, seconds);
  }
  const date = new Date(header);
  if (!Number.isNaN(date.getTime())) {
    const diff = Math.floor((date.getTime() - Date.now()) / 1000);
    return Math.max(0, diff);
  }
  return null;
}

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem("arqau_token");
}

function setToken(token: string) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem("arqau_token", token);
  if (typeof window !== "undefined") {
    window.dispatchEvent(new StorageEvent("storage", { key: "arqau_token", newValue: token }));
  }
}

function clearToken() {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem("arqau_token");
  if (typeof window !== "undefined") {
    window.dispatchEvent(new StorageEvent("storage", { key: "arqau_token", newValue: null }));
  }
}

const REFRESH_LOCK_NAME = "arqau_refresh_lock";
const REFRESH_CHANNEL_NAME = "arqau_refresh_channel";
const SESSION_VERSION_KEY = "arqau_session_version";

function getSessionVersion(): number {
  if (typeof window === "undefined") return 0;
  const v = window.localStorage.getItem(SESSION_VERSION_KEY);
  return v ? parseInt(v, 10) : 0;
}

function setSessionVersion(version: number): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(SESSION_VERSION_KEY, String(version));
  window.dispatchEvent(new StorageEvent("storage", { key: SESSION_VERSION_KEY, newValue: String(version) }));
}

let refreshPromise: Promise<boolean> | null = null;
let broadcastChannel: BroadcastChannel | null = null;

function getBroadcastChannel(): BroadcastChannel | null {
  if (typeof window === "undefined") return null;
  if (!broadcastChannel) {
    try {
      broadcastChannel = new BroadcastChannel(REFRESH_CHANNEL_NAME);
      broadcastChannel.onmessage = (event) => {
        if (event.data === "logout") {
          clearToken();
          refreshPromise = null;
        } else if (event.data === "refresh_success") {
          // Another tab refreshed successfully; invalidate local promise so next call re-checks
          refreshPromise = null;
        }
      };
    } catch {
      broadcastChannel = null;
    }
  }
  return broadcastChannel;
}

// Test-only: reset cached broadcast channel
export function __test_resetBroadcastChannel(): void {
  broadcastChannel = null;
}

function broadcastRefreshSuccess(): void {
  const ch = getBroadcastChannel();
  if (ch) ch.postMessage("refresh_success");
}

function broadcastLogout(): void {
  const ch = getBroadcastChannel();
  if (ch) ch.postMessage("logout");
}

async function withRefreshLock<T>(operation: () => Promise<T>): Promise<T> {
  if (typeof window === "undefined") {
    return operation();
  }

  if (navigator.locks) {
    // Web Locks API: exclusive lock per origin
    // The lock is held for the duration of the callback and released when it returns
    return await (navigator as any).locks.request(REFRESH_LOCK_NAME, { mode: "exclusive" }, async () => {
      return await operation();
    });
  }

  // Fallback: no lock available, proceed without cross-tab exclusion
  return operation();
}

async function doRefresh(): Promise<boolean> {
  try {
    const response = await fetch(`${BFF_BASE}/auth/refresh`, {
      method: "POST",
      credentials: "same-origin",
    });
    if (!response.ok) return false;
    const data = await response.json().catch(() => ({}));
    if (data.access_token) {
      setToken(data.access_token);
      return true;
    }
    return false;
  } catch {
    return false;
  }
}

async function refreshOnce(): Promise<boolean> {
  const versionBefore = getSessionVersion();

  // Fast path: if another tab already refreshed, re-check token
  if (refreshPromise) {
    try {
      const result = await refreshPromise;
      if (result && getToken()) return true;
    } catch {
      // Previous refresh failed; proceed to attempt our own
    }
  }

  return withRefreshLock(async () => {
    // Double-check inside lock using session version (reliable cross-tab signal)
    if (getSessionVersion() > versionBefore) {
      // Another tab already refreshed; our token should be valid
      if (getToken()) return true;
    }

    // Check if refreshPromise is still valid (from a previous attempt in this tab)
    if (refreshPromise) {
      try {
        const result = await refreshPromise;
        if (result && getToken()) return true;
      } catch {
        // Previous refresh failed; proceed to attempt our own
      }
    }

    refreshPromise = (async () => {
      try {
        const success = await doRefresh();
        if (success) {
          setSessionVersion(getSessionVersion() + 1);
          broadcastRefreshSuccess();
        }
        return success;
      } finally {
        refreshPromise = null;
      }
    })();

    return await refreshPromise;
  });
}

async function request<T>(
  path: string,
  options: RequestInit = {},
  retries = 1
): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string> || {}),
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const method = (options.method || "GET").toUpperCase();
  const isIdempotent = method === "GET" || method === "HEAD" || method === "OPTIONS";

  let lastError: Error | null = null;
  let attemptedRefresh = false;

  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      const response = await fetch(`${API_BASE}${path}`, {
        ...options,
        headers,
      });

      if (!response.ok) {
        const retryAfterHeader = response.headers?.get?.("Retry-After") ?? null;
        const retryAfter = parseRetryAfter(retryAfterHeader);

        if (response.status === 401 && !attemptedRefresh && !path.startsWith("/auth/")) {
          attemptedRefresh = true;
          const refreshed = await refreshOnce();
          if (refreshed) {
            const newToken = getToken();
            if (newToken) {
              headers["Authorization"] = `Bearer ${newToken}`;
              continue;
            }
          }
          clearToken();
          if (typeof window !== "undefined" && !window.location.pathname.startsWith("/login")) {
            window.location.href = "/login";
          }
        }

        if (response.status === 429) {
          const message = retryAfter !== null
            ? `Rate limited. Please try again in ${retryAfter} second${retryAfter === 1 ? "" : "s"}.`
            : "Rate limited. Please try again later.";
          throw new ApiError(message, 429, retryAfter);
        }

        if (response.status === 403) {
          throw new ApiError("Permission denied. You do not have access to this resource.", 403);
        }

        if (response.status >= 500 && response.status < 600) {
          const messages: Record<number, string> = {
            500: "Server error. Please try again later.",
            502: "Service temporarily unavailable. Please try again later.",
            503: "Service unavailable. Please try again later.",
            504: "Gateway timeout. Please try again later.",
          };
          const message = messages[response.status] || "Server error. Please try again later.";
          throw new ApiError(message, response.status);
        }

        const body = await response.json().catch(() => ({}));
        const detail = body?.detail || body?.message || `HTTP ${response.status}`;
        throw new ApiError(detail, response.status);
      }

      if (response.status === 204) {
        return undefined as T;
      }

      return response.json();
    } catch (err) {
      lastError = err instanceof Error ? err : new Error(String(err));

      // Retry on network errors only for idempotent requests; retry 429 for idempotent
      const shouldRetry = attempt < retries
        && !(lastError instanceof ApiError)
        && isIdempotent
        || (lastError instanceof ApiError
            && lastError.status === 429
            && isIdempotent
            && attempt < retries);

      if (shouldRetry) {
        await new Promise((resolve) => setTimeout(resolve, 500 * (attempt + 1)));
      } else {
        break;
      }
    }
  }

  throw lastError || new Error("Request failed");
}

export const api = {
  auth: {
    register: async (email: string, password: string, name?: string) => {
      const response = await fetch(`${BFF_BASE}/auth/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password, name }),
        credentials: "same-origin",
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        const detail = toReadableError(data?.error ?? data?.detail ?? data?.message, "Registration failed");
        throw new ApiError(detail, response.status);
      }
      if (data.access_token) setToken(data.access_token);
      return data;
    },
    login: async (email: string, password: string) => {
      const response = await fetch(`${BFF_BASE}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
        credentials: "same-origin",
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        const detail = toReadableError(data?.error ?? data?.detail ?? data?.message, "Login failed");
        throw new ApiError(detail, response.status);
      }
      if (data.access_token) setToken(data.access_token);
      return data;
    },
    logout: async () => {
      try {
        await fetch(`${BFF_BASE}/auth/logout`, {
          method: "POST",
          credentials: "same-origin",
        });
      } catch {
        // Ignore network errors; logout is best-effort
      } finally {
        clearToken();
        setSessionVersion(0);
        broadcastLogout();
      }
    },
    refresh: async () => {
      const response = await fetch(`${BFF_BASE}/auth/refresh`, {
        method: "POST",
        credentials: "same-origin",
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        const detail = data?.error || data?.detail || data?.message || "Token refresh failed";
        throw new ApiError(detail, response.status);
      }
      if (data.access_token) setToken(data.access_token);
      // BFF strips refresh_token from JSON response; return only access_token and rest
      const { refresh_token, ...rest } = data;
      return rest;
    },
    me: () => request<User>("/auth/me"),
  },

  employers: {
    // Creates a company for the authenticated user, who becomes its
    // employer_admin. Requires a valid access token (attached by `request`).
    create: (data: EmployerCreate) =>
      request<EmployerRead>("/employers/", {
        method: "POST",
        body: JSON.stringify(data),
      }),
    // The employer the caller administers, resolved server-side from their
    // EmployerAdmin membership. Returns 404 when the account has no employer.
    mine: () => request<EmployerRead>("/employers/mine"),
    get: (employerId: string) =>
      request<EmployerRead>(`/employers/${encodeURIComponent(employerId)}`),
    getPolicy: (employerId: string) =>
      request<EwaPolicyRead>(`/employers/${encodeURIComponent(employerId)}/ewa/policy`),
    listRequests: (employerId: string, status?: string) => {
      const query = status ? `?status_filter=${encodeURIComponent(status)}` : "";
      // NOTE: this route lives under the /ewa router prefix.
      return request<WageAccessRequestRead[]>(
        `/ewa/employers/${encodeURIComponent(employerId)}/requests${query}`,
      );
    },
  },

  employees: {
    // Creates an Employee record for an existing ARQAU user. The caller must
    // have employer scope (EmployerAdmin membership); the service rejects
    // unknown users and duplicate profiles.
    create: (data: {
      user_id: string;
      display_name?: string;
      external_employee_id?: string;
      status?: string;
    }) =>
      request<EmployeeRead>("/employees/", {
        method: "POST",
        body: JSON.stringify(data),
      }),
  },

  employments: {
    // Links an Employee to the caller's employer. employer_id is derived
    // server-side from /employers/mine and re-validated against scope.
    create: (data: {
      employee_id: string;
      employer_id: string;
      employment_type?: string;
      status?: string;
      start_date?: string;
      end_date?: string;
      eligible_from?: string;
      eligible_to?: string;
    }) =>
      request<EmploymentRead>("/employments/", {
        method: "POST",
        body: JSON.stringify(data),
      }),
  },

  salary: {
    // One salary profile per employment. employment must be in scope.
    create: (data: {
      employment_id: string;
      currency: string;
      monthly_salary_amount_minor: number;
      pay_schedule: string;
      payday_day?: number;
      effective_from: string;
      effective_to?: string;
    }) =>
      request<SalaryProfileRead>("/salary-profiles/", {
        method: "POST",
        body: JSON.stringify(data),
      }),
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
    getCalculation: () => request<EWAResultResponse>("/ewa/calculation"),
    createRequest: (data: { amount_minor: number; reason?: string; idempotencyKey?: string }) =>
      request<WageAccessRequest>("/ewa/request", {
        method: "POST",
        body: JSON.stringify({
          amount_minor: data.amount_minor,
          reason: data.reason,
          idempotency_key: data.idempotencyKey,
        }),
      }),
    getRequests: () => request<WageAccessRequest[]>("/ewa/requests"),
  },

  financial: {
    // Authoritative, read-only financial context for the authenticated user.
    // Identity comes exclusively from the access token; no caller-controlled
    // user_id / employee_id / employer_id selectors are sent.
    getContext: () => request<FinancialContext>("/financial/context"),

    // Deterministic, read-only analysis of a hypothetical withdrawal amount.
    // Strictly amount_minor, server-resolved identity. Never creates, reserves
    // or mutates anything: actual withdrawals require POST /ewa/request.
    analyzeScenario: (amount_minor: number) =>
      request<WithdrawalAnalysis>("/financial/withdrawal-analysis", {
        method: "POST",
        body: JSON.stringify({ amount_minor }),
      }),
  },

  ai: {
    analyzeWithdrawal: (amount_tenge: number) =>
      request<WithdrawalDecisionResponse>("/financial/withdrawal-decision", {
        method: "POST",
        body: JSON.stringify({ amount_minor: Math.round(amount_tenge * 100) }),
      }),
    chat: (message: string, conversation_id?: string) =>
      request<CopilotResponse>("/ai/chat", {
        method: "POST",
        body: JSON.stringify({ message, conversation_id }),
      }),
    demo: {
      chat: (message: string, conversation_id?: string) =>
        request<CopilotResponse>("/demo/ai/chat", {
          method: "POST",
          body: JSON.stringify({ message, conversation_id }),
        }),
    },
  },
};

export { getToken, setToken, clearToken, ApiError, broadcastRefreshSuccess, broadcastLogout, doRefresh, refreshOnce, request, withRefreshLock, getSessionVersion, setSessionVersion };
