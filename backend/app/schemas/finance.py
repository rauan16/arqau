from pydantic import BaseModel
from typing import Optional


class TransactionCreate(BaseModel):
    type: str
    amount_minor: int
    category: Optional[str] = None
    merchant: Optional[str] = None
    description: Optional[str] = None


class TransactionResponse(BaseModel):
    id: str
    user_id: str
    type: str
    amount_minor: int
    category: Optional[str] = None
    merchant: Optional[str] = None
    description: Optional[str] = None
    date: Optional[str] = None
    created_at: Optional[str] = None

    model_config = {"from_attributes": True}


class FinanceSummary(BaseModel):
    total_income_minor: int
    total_expense_minor: int
    net_balance_minor: int
    transaction_count: int


class BudgetCreate(BaseModel):
    category: str
    limit_minor: int
    period: Optional[str] = "monthly"


class BudgetResponse(BaseModel):
    id: str
    user_id: str
    category: str
    limit_minor: int
    spent_minor: int
    period: str
    remaining_minor: int

    model_config = {"from_attributes": True}


class GoalCreate(BaseModel):
    title: str
    target_minor: int
    current_minor: Optional[int] = 0
    deadline: Optional[str] = None


class GoalResponse(BaseModel):
    id: str
    user_id: str
    title: str
    target_minor: int
    current_minor: int
    deadline: Optional[str] = None
    status: str
    progress_pct: int

    model_config = {"from_attributes": True}
