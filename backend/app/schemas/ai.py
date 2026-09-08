from pydantic import BaseModel
from typing import Optional


class WithdrawalAnalysis(BaseModel):
    withdrawal_amount: int
    remaining_amount: int
    available_amount: int
    earned_amount: int
    accessed_amount: int
    total_income: int
    total_expenses: int
    net_balance: int
    covered_expenses: bool
    reserve_status: str
    risk_level: str
    recommendation: str
    explanation: str
    disclaimer: str


class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None


class ChatResponse(BaseModel):
    response: str
    disclaimer: str
