from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.database import get_db
from app.models import User, Transaction, EarnedWages
from app.schemas.ai import WithdrawalAnalysis, ChatRequest, ChatResponse
from app.services.ai_service import analyze_withdrawal, chat_with_user
from app.api.v1.auth import get_current_user
from app.config import get_settings
from openai import OpenAI, APIStatusError, RateLimitError
import json

settings = get_settings()
router = APIRouter(prefix="/ai", tags=["ai"])


@router.get("/diagnostic")
async def ai_diagnostic():
    key_present = bool(settings.openai_api_key)
    result = {
        "openai_api_key_present": key_present,
        "openai_model": settings.openai_model,
    }
    if not key_present:
        result["status"] = "no_key"
        return result

    client = OpenAI(api_key=settings.openai_api_key)
    try:
        completion = client.chat.completions.create(
            model=settings.openai_model,
            messages=[{"role": "user", "content": "Reply with exactly: diagnostic-ok"}],
            max_tokens=10,
        )
        result["status"] = "ok"
        result["provider_status"] = completion.choices[0].message.content.strip() if completion.choices else "empty"
        return result
    except RateLimitError as e:
        result["status"] = "error"
        result["error_type"] = "rate_limit"
        result["error_code"] = "rate_limit"
        result["http_status"] = 429
        result["sanitized_message"] = str(e)[:200]
        return result
    except APIStatusError as e:
        result["status"] = "error"
        result["error_type"] = "api_status"
        result["error_code"] = e.code or "unknown"
        result["http_status"] = e.status_code
        result["sanitized_message"] = str(e)[:200]
        return result
    except Exception as e:
        result["status"] = "error"
        result["error_type"] = "unexpected"
        result["error_code"] = "unknown"
        result["http_status"] = None
        result["sanitized_message"] = str(e)[:200]
        return result


@router.post("/analyze-withdrawal", response_model=WithdrawalAnalysis)
async def analyze_withdrawal_endpoint(
    request: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    withdrawal_amount = request.get("withdrawal_amount")
    if withdrawal_amount is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="withdrawal_amount is required")
    try:
        withdrawal_amount = int(withdrawal_amount)
    except (TypeError, ValueError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="withdrawal_amount must be an integer")
    if withdrawal_amount <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="withdrawal_amount must be positive")

    ew_result = await db.execute(select(EarnedWages).where(EarnedWages.user_id == current_user.id))
    ew = ew_result.scalar_one_or_none()
    if not ew:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No earned wages found. Set earned wages first.")

    available = ew.available_amount_minor
    if withdrawal_amount > available:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Amount exceeds available balance of {available} ₸")

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
    total_income = income_result.scalar() or 0
    total_expenses = expense_result.scalar() or 0
    net_balance = total_income - total_expenses

    financial_context = {
        "earned_amount": ew.earned_amount_minor,
        "accessed_amount": ew.accessed_amount_minor,
        "available_amount": available,
        "withdrawal_amount": withdrawal_amount,
        "total_income": total_income,
        "total_expenses": total_expenses,
        "net_balance": net_balance,
    }

    if not settings.openai_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI service is not configured. Please contact support.",
        )

    try:
        result = await analyze_withdrawal(financial_context)
        return WithdrawalAnalysis(**result)
    except RuntimeError as e:
        if "AI_QUOTA_EXCEEDED" in str(e):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="AI analysis is temporarily unavailable due to service limits. Please try again later.",
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="AI analysis is temporarily unavailable. Please try again later.",
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="AI analysis is temporarily unavailable. Please try again later.",
        )


@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    ew_result = await db.execute(select(EarnedWages).where(EarnedWages.user_id == current_user.id))
    ew = ew_result.scalar_one_or_none()
    earned_amount = ew.earned_amount_minor if ew else 0
    accessed_amount = ew.accessed_amount_minor if ew else 0
    available_amount = ew.available_amount_minor if ew else 0

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
    total_income = income_result.scalar() or 0
    total_expenses = expense_result.scalar() or 0
    net_balance = total_income - total_expenses

    financial_context = {
        "earned_amount": earned_amount,
        "accessed_amount": accessed_amount,
        "available_amount": available_amount,
        "total_income": total_income,
        "total_expenses": total_expenses,
        "net_balance": net_balance,
    }

    if not settings.openai_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI service is not configured. Please contact support.",
        )

    try:
        result = await chat_with_user(request.message, financial_context)
        return ChatResponse(**result)
    except RuntimeError as e:
        if "AI_QUOTA_EXCEEDED" in str(e):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="AI assistant is temporarily unavailable due to service limits. Please try again later.",
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="AI assistant is temporarily unavailable. Please try again later.",
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="AI assistant is temporarily unavailable. Please try again later.",
        )
