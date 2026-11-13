"""Demo financial context service for the public AI chat.

Computes the demo financial snapshot from trusted server-side seed data
(never from client input). Mirrors the TypeScript `lib/demoFinancialContext`
so backend and frontend stay consistent.

Read-only: no database writes, no financial mutations, no real account access.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

# ---------------------------------------------------------------------------
# Demo seed data (single source of truth, matches lib/demoStore.ts seed)
# ---------------------------------------------------------------------------

DEMO_CURRENCY = "KZT"
DEMO_DATA_SOURCE = "demo"

DEMO_SALARY = 187_400
DEMO_EARNED = 212_800
DEMO_AVAILABLE = 120_000
DEMO_RESERVE_TARGET = 60_000
DEMO_DAYS_TO_PAYDAY = 22
DEMO_PAYDAY_DATE = "2026-10-16"

DEMO_UPCOMING_BILLS: list[dict[str, Any]] = [
    {"id": "rent", "amount": 45_000, "due_date": "2026-11-01", "is_paid": False},
    {"id": "utilities", "amount": 9_000, "due_date": "2026-11-05", "is_paid": False},
    {"id": "phone", "amount": 3_400, "due_date": "2026-11-07", "is_paid": False},
]

DEMO_TRANSACTIONS: list[dict[str, Any]] = [
    {"id": "seed-1", "type": "income", "amount": 150_000, "category": "Salary", "merchant": "Employer payroll", "date": "2026-09-16", "description": "Advance paid on payday"},
    {"id": "seed-2", "type": "expense", "amount": 45_000, "category": "Housing", "merchant": "Home Rent", "date": "2026-09-17"},
    {"id": "seed-3", "type": "expense", "amount": 25_000, "category": "Food", "merchant": "City Market", "date": "2026-09-21"},
    {"id": "seed-4", "type": "expense", "amount": 15_000, "category": "Transport", "merchant": "Metro Pass", "date": "2026-09-25"},
    {"id": "seed-5", "type": "income", "amount": 37_400, "category": "Salary", "merchant": "Employer payroll", "date": "2026-10-02", "description": "Second payday of the cycle"},
    {"id": "seed-6", "type": "expense", "amount": 12_400, "category": "Food", "merchant": "City Market", "date": "2026-10-05"},
    {"id": "seed-7", "type": "expense", "amount": 6_500, "category": "Lifestyle", "merchant": "Streaming Plus", "date": "2026-10-07"},
    {"id": "seed-8", "type": "expense", "amount": 13_000, "category": "Health", "merchant": "Pharmacy", "date": "2026-10-09"},

    # New period (16 Oct – 25 Oct demo snapshot)
    {"id": "seed-21", "type": "income", "amount": 187_400, "category": "Salary", "merchant": "Employer payroll", "date": "2026-10-16", "description": "Salary"},
    {"id": "seed-22", "type": "expense", "amount": 45_000, "category": "Housing", "merchant": "Home Rent", "date": "2026-10-17"},
    {"id": "seed-23", "type": "expense", "amount": 22_000, "category": "Food", "merchant": "City Market", "date": "2026-10-20"},
    {"id": "seed-24", "type": "expense", "amount": 14_000, "category": "Transport", "merchant": "Metro Pass", "date": "2026-10-24"},

    {"id": "seed-9", "type": "income", "amount": 187_400, "category": "Salary", "merchant": "Employer payroll", "date": "2026-08-17"},
    {"id": "seed-10", "type": "expense", "amount": 45_000, "category": "Housing", "merchant": "Home Rent", "date": "2026-08-18"},
    {"id": "seed-11", "type": "expense", "amount": 23_000, "category": "Food", "merchant": "City Market", "date": "2026-08-22"},
    {"id": "seed-12", "type": "expense", "amount": 14_000, "category": "Transport", "merchant": "Metro Pass", "date": "2026-08-26"},
    {"id": "seed-13", "type": "expense", "amount": 12_000, "category": "Food", "merchant": "Bakery", "date": "2026-09-02"},
    {"id": "seed-14", "type": "expense", "amount": 3_990, "category": "Lifestyle", "merchant": "Streaming Plus", "date": "2026-09-05"},
    {"id": "seed-15", "type": "income", "amount": 187_400, "category": "Salary", "merchant": "Employer payroll", "date": "2026-07-17"},
    {"id": "seed-16", "type": "expense", "amount": 45_000, "category": "Housing", "merchant": "Home Rent", "date": "2026-07-18"},
    {"id": "seed-17", "type": "expense", "amount": 21_000, "category": "Food", "merchant": "City Market", "date": "2026-07-23"},
    {"id": "seed-18", "type": "expense", "amount": 16_000, "category": "Transport", "merchant": "Metro Pass", "date": "2026-07-28"},
    {"id": "seed-19", "type": "expense", "amount": 8_000, "category": "Health", "merchant": "Pharmacy", "date": "2026-08-04"},
    {"id": "seed-20", "type": "expense", "amount": 3_990, "category": "Lifestyle", "merchant": "Streaming Plus", "date": "2026-08-06"},
]


# ---------------------------------------------------------------------------
# Pure computation helpers
# ---------------------------------------------------------------------------

def _compute_current_period_totals() -> dict[str, int]:
    """Income and expense for the current pay period (payday_date onward)."""
    period_start = DEMO_PAYDAY_DATE
    income = 0
    expense = 0
    for tx in DEMO_TRANSACTIONS:
        if tx["date"] >= period_start:
            if tx["type"] == "income":
                income += tx["amount"]
            else:
                expense += tx["amount"]
    return {"income": income, "expense": expense, "net": income - expense}


def _compute_current_period_top_categories() -> list[dict[str, Any]]:
    """Compute top spending categories for the current pay period only.
    
    Matches the same period boundaries and expense filtering as total_spending_minor.
    Returns list sorted by amount descending, then category name, limited to 5.
    """
    period_start = DEMO_PAYDAY_DATE
    cat_totals: dict[str, dict[str, int]] = {}
    for tx in DEMO_TRANSACTIONS:
        if tx["date"] >= period_start and tx["type"] == "expense":
            cat = tx["category"]
            if cat not in cat_totals:
                cat_totals[cat] = {"amount": 0, "count": 0}
            cat_totals[cat]["amount"] += tx["amount"]
            cat_totals[cat]["count"] += 1
    ordered = sorted(cat_totals.items(), key=lambda x: (-x[1]["amount"], x[0]))[:5]
    return [
        {"category": cat, "amount_minor": data["amount"] * 100, "transaction_count": data["count"]}
        for cat, data in ordered
    ]


def _compute_upcoming_total() -> int:
    return sum(b["amount"] for b in DEMO_UPCOMING_BILLS)


def _compute_upcoming_unpaid_total() -> int:
    return sum(b["amount"] for b in DEMO_UPCOMING_BILLS if not b["is_paid"])


def _compute_reserve_saved(current_period: dict[str, int]) -> int:
    """Anything earned but not spent in the current period is treated as saved."""
    return max(0, DEMO_EARNED - current_period["expense"])


# ---------------------------------------------------------------------------
# Financial context
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DemoFinancialContext:
    available_amount: int
    earned_amount: int
    salary_amount: int
    income_amount: int
    expense_amount: int
    net_amount: int
    upcoming_bills: list[dict[str, Any]]
    upcoming_bills_total: int
    upcoming_bills_unpaid_total: int
    reserve_target: int
    reserve_saved: int
    reserve_remaining: int
    reserve_progress: float
    payday_date: str
    days_to_payday: int
    currency: str
    data_as_of: str
    source: str
    is_demo: bool
    warnings: list[str]


def build_demo_financial_context() -> DemoFinancialContext:
    """Build the unified demo financial context from trusted seed data."""
    current_period = _compute_current_period_totals()
    bills_total = _compute_upcoming_total()
    bills_unpaid_total = _compute_upcoming_unpaid_total()
    reserve_saved = _compute_reserve_saved(current_period)
    reserve_remaining = max(0, DEMO_RESERVE_TARGET - reserve_saved)
    reserve_progress = min(1.0, reserve_saved / DEMO_RESERVE_TARGET) if DEMO_RESERVE_TARGET > 0 else 0.0

    warnings: list[str] = []
    if DEMO_AVAILABLE <= 0:
        warnings.append("No EWA capacity is currently available.")
    if bills_unpaid_total > 0 and DEMO_AVAILABLE < bills_unpaid_total:
        warnings.append("Available amount does not cover unpaid upcoming bills.")
    if reserve_progress < 1:
        warnings.append(f"Reserve is below target by {reserve_remaining} tenge.")

    return DemoFinancialContext(
        available_amount=DEMO_AVAILABLE,
        earned_amount=DEMO_EARNED,
        salary_amount=DEMO_SALARY,
        income_amount=current_period["income"],
        expense_amount=current_period["expense"],
        net_amount=current_period["net"],
        upcoming_bills=DEMO_UPCOMING_BILLS,
        upcoming_bills_total=bills_total,
        upcoming_bills_unpaid_total=bills_unpaid_total,
        reserve_target=DEMO_RESERVE_TARGET,
        reserve_saved=reserve_saved,
        reserve_remaining=reserve_remaining,
        reserve_progress=reserve_progress,
        payday_date=DEMO_PAYDAY_DATE,
        days_to_payday=DEMO_DAYS_TO_PAYDAY,
        currency=DEMO_CURRENCY,
        data_as_of=datetime.utcnow().isoformat() + "Z",
        source=DEMO_DATA_SOURCE,
        is_demo=True,
        warnings=warnings,
    )


# ---------------------------------------------------------------------------
# Affordability evaluation
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DemoAffordabilityResult:
    amount: int
    status: str  # "comfortable" | "caution" | "high-risk"
    remaining_available: int
    buffer_after_bills: int
    requestable: bool
    share_of_earned: float
    reason: str | None = None


def evaluate_demo_affordability(amount: int) -> DemoAffordabilityResult:
    """Evaluate a hypothetical amount against available, bills and reserve."""
    ctx = build_demo_financial_context()
    remaining_available = max(0, ctx.available_amount - amount)
    buffer_after_bills = remaining_available - ctx.upcoming_bills_unpaid_total

    if buffer_after_bills >= ctx.reserve_target:
        status = "comfortable"
    elif buffer_after_bills >= 0:
        status = "caution"
    else:
        status = "high-risk"

    requestable = amount > 0 and amount <= ctx.available_amount and buffer_after_bills >= 0

    reason: str | None = None
    if not requestable:
        if status == "high-risk":
            reason = "This amount would leave upcoming bills uncovered."
        elif status == "caution":
            reason = "This amount would reduce your reserve below target."
        else:
            reason = "Amount is not requestable."

    share_of_earned = min(1.0, amount / ctx.earned_amount) if ctx.earned_amount > 0 else 0.0

    return DemoAffordabilityResult(
        amount=amount,
        status=status,
        remaining_available=remaining_available,
        buffer_after_bills=buffer_after_bills,
        requestable=requestable,
        share_of_earned=share_of_earned,
        reason=reason,
    )


# ---------------------------------------------------------------------------
# Sanitized provider input (allow-list, server-owned facts only)
# ---------------------------------------------------------------------------

def build_demo_sanitized_input(analysis: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build the minimal allow-listed provider payload from demo context.

    Never accepts caller-supplied financial values. All numbers come from
    server-side seed data.
    """
    ctx = build_demo_financial_context()

    raw: dict[str, Any] = {
        "salary_amount_minor": ctx.salary_amount * 100,
        "currency": ctx.currency,
        "pay_period_start": ctx.payday_date,
        "pay_period_end": "2026-11-16",
        "calculation_date": "2026-10-25",
        "earned_amount_minor": ctx.earned_amount * 100,
        "policy_limit_minor": 0,
        "reserved_amount_minor": 0,
        "paid_amount_minor": 0,
        "available_amount_minor": 0,
        "max_requestable_amount_minor": 0,
        "minimum_withdrawal_minor": None,
        "maximum_withdrawal_minor": None,
        "eligible": False,
        "eligibility_reasons": ["NO_EWA_POLICY"],
        "can_request_withdrawal": False,
        "withdrawals_this_period": 0,
        "max_withdrawals_per_period": None,
        "total_withdrawal_requests": 0,
        "pending_withdrawal_count": 0,
        "approved_withdrawal_count": 0,
        "paid_withdrawal_count": 0,
        "requested_withdrawal_amount_minor": 0,
        "paid_withdrawal_amount_minor": 0,
        "spending_available": True,
        "total_spending_minor": ctx.expense_amount * 100,
        "transaction_count": 8,
        "essential_spending_minor": None,
        "discretionary_spending_minor": None,
        "top_spending_categories": _compute_current_period_top_categories(),
        "budget_available": False,
        "budget_total_minor": None,
        "budget_spent_minor": None,
        "budget_remaining_minor": None,
        "goals_available": False,
        "active_goals_count": 0,
        "total_goal_target_minor": None,
        "total_goal_saved_minor": None,
        "has_salary_profile": True,
        "has_ewa_policy": False,
        "has_transactions": True,
        "has_budget": False,
        "has_goals": False,
        "missing_data": [],
        "availability_note": (
            "available_amount_minor is deterministic remaining EWA capacity in tiyin "
            "(100 tiyin = 1 KZT). To express in KZT, divide by 100. "
            "Not a recommended amount."
        ),
        "period_net_surplus_minor": ctx.reserve_saved * 100,
        "reserve_target_minor": ctx.reserve_target * 100,
        "reserve_shortfall_minor": ctx.reserve_remaining * 100,
        "reserve_progress_ratio": ctx.reserve_progress,
        "days_to_payday": ctx.days_to_payday,
        "payday_date": ctx.payday_date,
        "income_amount_minor": ctx.income_amount * 100,
        "net_amount_minor": ctx.net_amount * 100,
    }

    if analysis is not None:
        raw.update({
            "analyzed_withdrawal_amount_minor": analysis["amount"] * 100,
            "analyzed_withdrawal_requestable": analysis["requestable"],
            "analyzed_withdrawal_blocking_reasons": [analysis["reason"]] if analysis["reason"] else [],
            "analyzed_remaining_available_minor": analysis["remaining_available"] * 100,
            "analyzed_remaining_max_requestable_minor": analysis["remaining_available"] * 100,
            "analyzed_exposure_after_minor": analysis["amount"] * 100,
            "analyzed_withdrawal_share_of_earned_bps": round(analysis["share_of_earned"] * 10000),
        })

    return raw
