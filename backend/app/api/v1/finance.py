from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.database import get_db
from app.models import User, Transaction, Budget, Goal
from app.schemas.finance import (
    TransactionCreate, TransactionResponse, FinanceSummary,
    BudgetCreate, BudgetResponse, GoalCreate, GoalResponse
)
from app.api.v1.auth import get_current_user
import uuid
from datetime import datetime

router = APIRouter(tags=["finance"])


@router.get("/finance/summary", response_model=FinanceSummary)
async def get_summary(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    income_result = await db.execute(
        select(func.coalesce(func.sum(Transaction.amount_minor), 0)).where(
            Transaction.user_id == current_user.id, Transaction.type == "income"
        )
    )
    expense_result = await db.execute(
        select(func.coalesce(func.sum(Transaction.amount_minor), 0)).where(
            Transaction.user_id == current_user.id, Transaction.type == "expense"
        )
    )
    count_result = await db.execute(
        select(func.count(Transaction.id)).where(Transaction.user_id == current_user.id)
    )
    total_income = income_result.scalar() or 0
    total_expense = expense_result.scalar() or 0
    transaction_count = count_result.scalar() or 0
    return FinanceSummary(
        total_income_minor=total_income,
        total_expense_minor=total_expense,
        net_balance_minor=total_income - total_expense,
        transaction_count=transaction_count,
    )


@router.get("/transactions", response_model=list[TransactionResponse])
async def get_transactions(limit: int = 100, offset: int = 0, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Transaction).where(Transaction.user_id == current_user.id).order_by(Transaction.created_at.desc()).limit(limit).offset(offset)
    )
    txs = result.scalars().all()
    return [
        TransactionResponse(
            id=tx.id,
            user_id=tx.user_id,
            type=tx.type,
            amount_minor=tx.amount_minor,
            category=tx.category,
            merchant=tx.merchant,
            description=tx.description,
            date=tx.date,
            created_at=tx.created_at.isoformat() if tx.created_at else None,
        )
        for tx in txs
    ]


@router.post("/transactions", response_model=TransactionResponse)
async def create_transaction(data: TransactionCreate, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    tx = Transaction(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        type=data.type,
        amount_minor=data.amount_minor,
        category=data.category,
        merchant=data.merchant,
        description=data.description,
        date=datetime.utcnow().isoformat(),
    )
    db.add(tx)
    await db.commit()
    await db.refresh(tx)
    return TransactionResponse(
        id=tx.id,
        user_id=tx.user_id,
        type=tx.type,
        amount_minor=tx.amount_minor,
        category=tx.category,
        merchant=tx.merchant,
        description=tx.description,
        date=tx.date,
        created_at=tx.created_at.isoformat() if tx.created_at else None,
    )


@router.put("/transactions/{tx_id}", response_model=TransactionResponse)
async def update_transaction(tx_id: str, data: dict, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Transaction).where(Transaction.id == tx_id, Transaction.user_id == current_user.id))
    tx = result.scalar_one_or_none()
    if not tx:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")
    allowed = {"type", "amount_minor", "category", "merchant", "description", "date"}
    for key, value in data.items():
        if key not in allowed:
            continue
        if key == "amount_minor" and (not isinstance(value, int) or value <= 0):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="amount_minor must be a positive integer")
        if key == "type" and value not in ("income", "expense"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="type must be 'income' or 'expense'")
        setattr(tx, key, value)
    await db.commit()
    await db.refresh(tx)
    return TransactionResponse(
        id=tx.id,
        user_id=tx.user_id,
        type=tx.type,
        amount_minor=tx.amount_minor,
        category=tx.category,
        merchant=tx.merchant,
        description=tx.description,
        date=tx.date,
        created_at=tx.created_at.isoformat() if tx.created_at else None,
    )


@router.delete("/transactions/{tx_id}")
async def delete_transaction(tx_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Transaction).where(Transaction.id == tx_id, Transaction.user_id == current_user.id))
    tx = result.scalar_one_or_none()
    if not tx:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")
    await db.delete(tx)
    await db.commit()
    return None


@router.get("/budgets", response_model=list[BudgetResponse])
async def get_budgets(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Budget).where(Budget.user_id == current_user.id))
    budgets = result.scalars().all()
    return [
        BudgetResponse(
            id=b.id,
            user_id=b.user_id,
            category=b.category,
            limit_minor=b.limit_minor,
            spent_minor=b.spent_minor,
            period=b.period,
            remaining_minor=b.limit_minor - b.spent_minor,
        )
        for b in budgets
    ]


@router.post("/budgets", response_model=BudgetResponse)
async def create_budget(data: BudgetCreate, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    budget = Budget(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        category=data.category,
        limit_minor=data.limit_minor,
        period=data.period or "monthly",
    )
    db.add(budget)
    await db.commit()
    await db.refresh(budget)
    return BudgetResponse(
        id=budget.id,
        user_id=budget.user_id,
        category=budget.category,
        limit_minor=budget.limit_minor,
        spent_minor=budget.spent_minor,
        period=budget.period,
        remaining_minor=budget.limit_minor - budget.spent_minor,
    )


@router.put("/budgets/{budget_id}", response_model=BudgetResponse)
async def update_budget(budget_id: str, data: dict, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Budget).where(Budget.id == budget_id, Budget.user_id == current_user.id))
    budget = result.scalar_one_or_none()
    if not budget:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Budget not found")
    for key, value in data.items():
        if hasattr(budget, key):
            setattr(budget, key, value)
    await db.commit()
    await db.refresh(budget)
    return BudgetResponse(
        id=budget.id,
        user_id=budget.user_id,
        category=budget.category,
        limit_minor=budget.limit_minor,
        spent_minor=budget.spent_minor,
        period=budget.period,
        remaining_minor=budget.limit_minor - budget.spent_minor,
    )


@router.delete("/budgets/{budget_id}")
async def delete_budget(budget_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Budget).where(Budget.id == budget_id, Budget.user_id == current_user.id))
    budget = result.scalar_one_or_none()
    if not budget:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Budget not found")
    await db.delete(budget)
    await db.commit()
    return None


@router.get("/goals", response_model=list[GoalResponse])
async def get_goals(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Goal).where(Goal.user_id == current_user.id))
    goals = result.scalars().all()
    return [
        GoalResponse(
            id=g.id,
            user_id=g.user_id,
            title=g.title,
            target_minor=g.target_minor,
            current_minor=g.current_minor,
            deadline=g.deadline,
            status=g.status,
            progress_pct=g.progress_pct,
        )
        for g in goals
    ]


@router.post("/goals", response_model=GoalResponse)
async def create_goal(data: GoalCreate, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    progress_pct = 0
    if data.target_minor > 0:
        progress_pct = min(100, int((data.current_minor or 0) / data.target_minor * 100))
    goal = Goal(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        title=data.title,
        target_minor=data.target_minor,
        current_minor=data.current_minor or 0,
        deadline=data.deadline,
        status="active",
        progress_pct=progress_pct,
    )
    db.add(goal)
    await db.commit()
    await db.refresh(goal)
    return GoalResponse(
        id=goal.id,
        user_id=goal.user_id,
        title=goal.title,
        target_minor=goal.target_minor,
        current_minor=goal.current_minor,
        deadline=goal.deadline,
        status=goal.status,
        progress_pct=goal.progress_pct,
    )


@router.put("/goals/{goal_id}", response_model=GoalResponse)
async def update_goal(goal_id: str, data: dict, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Goal).where(Goal.id == goal_id, Goal.user_id == current_user.id))
    goal = result.scalar_one_or_none()
    if not goal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Goal not found")
    for key, value in data.items():
        if not hasattr(goal, key):
            continue
        setattr(goal, key, value)
        if key in ("target_minor", "current_minor") and goal.target_minor > 0:
            goal.progress_pct = min(100, int((goal.current_minor or 0) / goal.target_minor * 100))
    await db.commit()
    await db.refresh(goal)
    return GoalResponse(
        id=goal.id,
        user_id=goal.user_id,
        title=goal.title,
        target_minor=goal.target_minor,
        current_minor=goal.current_minor,
        deadline=goal.deadline,
        status=goal.status,
        progress_pct=goal.progress_pct,
    )


@router.delete("/goals/{goal_id}")
async def delete_goal(goal_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Goal).where(Goal.id == goal_id, Goal.user_id == current_user.id))
    goal = result.scalar_one_or_none()
    if not goal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Goal not found")
    await db.delete(goal)
    await db.commit()
    return None
