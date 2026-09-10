from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.database import get_db
from app.models import User, Transaction, EarnedWages
from app.schemas.ai import WithdrawalAnalysis, ChatRequest, ChatResponse
from app.services.ai_service import analyze_withdrawal, chat_with_user
from app.api.v1.auth import get_current_user
from app.config import get_settings

settings = get_settings()
router = APIRouter(prefix="/ai", tags=["ai"])


@router.get("/diagnostic")
async def ai_diagnostic():
    """TEMPORARY diagnostic endpoint.

    Returns the exact provider error so the root cause of AI failures can be
    determined. Never returns the API key or Authorization header.
    """
    from openai import OpenAI, APIStatusError, RateLimitError
    import re as _re

    key_present = bool(settings.openai_api_key)
    result = {
        "openai_api_key_present": key_present,
        "openai_model": settings.openai_model,
        "base_url": "https://openrouter.ai/api/v1" if (settings.openai_api_key or "").startswith("sk-or-") else "default",
    }
    if not key_present:
        result["status"] = "no_key"
        return result

    client = OpenAI(
        api_key=settings.openai_api_key,
        base_url="https://openrouter.ai/api/v1" if (settings.openai_api_key or "").startswith("sk-or-") else None,
        timeout=30.0,
    )
    try:
        completion = client.chat.completions.create(
            model=settings.openai_model,
            messages=[{"role": "user", "content": "Reply with exactly: diagnostic-ok"}],
            max_tokens=10,
        )
        result["status"] = "ok"
        result["provider_response"] = (completion.choices[0].message.content.strip() if completion.choices else "empty")
        return result
    except RateLimitError as e:
        result["status"] = "error"
        result["http_status"] = 429
        result["error_category"] = "rate_limit"
        result["error_code"] = "rate_limit"
        result["error_message"] = _scrub(str(e))
        result["response_body"] = _scrub(getattr(getattr(e, "response", None), "text", "") or "")
        return result
    except APIStatusError as e:
        result["status"] = "error"
        result["http_status"] = e.status_code
        result["error_code"] = getattr(e, "code", None) or "unknown"
        body = getattr(getattr(e, "response", None), "text", "") or ""
        result["error_message"] = _scrub(str(e))
        result["response_body"] = _scrub(body)
        if e.status_code == 429:
            result["error_category"] = "rate_limit"
        elif e.status_code == 402:
            result["error_category"] = "credits_payment_quota"
        elif e.status_code in (401, 403):
            result["error_category"] = "authentication"
        elif e.status_code == 400:
            result["error_category"] = "bad_request_model_parameters"
        elif 500 <= e.status_code < 600:
            result["error_category"] = "provider_server_error"
        else:
            result["error_category"] = "other"
        return result
    except Exception as e:
        result["status"] = "error"
        result["http_status"] = None
        result["error_category"] = "non_http_exception"
        result["error_type"] = type(e).__name__
        result["error_message"] = _scrub(str(e))
        return result


def _scrub(text):
    """Remove any API key / auth header value from diagnostic output."""
    if not text:
        return ""
    text = _re.sub(r"(?i)(sk-or-[A-Za-z0-9_\-]+)", "[REDACTED_KEY]", text)
    text = _re.sub(r"(?i)(sk-[A-Za-z0-9_\-]+)", "[REDACTED_KEY]", text)
    text = _re.sub(r"(?i)(authorization[\"'\s:=]+)[^\s,}}\"]+", r"\1[REDACTED]", text)
    text = _re.sub(r"(?i)(api[_-]?key[\"'\s:=]+)[^\s,}}\"]+", r"\1[REDACTED]", text)
    return text


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
        msg = str(e)
        if msg == "AI_QUOTA_EXCEEDED":
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="AI analysis is temporarily unavailable due to service limits. Please try again later.",
            )
        if msg == "AI_CREDITS_EXCEEDED":
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="AI analysis is temporarily unavailable due to service limits. Please try again later.",
            )
        if msg == "AI_AUTH_FAILED":
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="AI service is temporarily misconfigured. Please contact support.",
            )
        if msg == "AI_TIMEOUT":
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="AI analysis timed out. Please try again.",
            )
        if msg == "AI_CONNECTION_ERROR":
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="AI service is temporarily unreachable. Please try again later.",
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
        msg = str(e)
        if msg == "AI_QUOTA_EXCEEDED":
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="AI assistant is temporarily unavailable due to service limits. Please try again later.",
            )
        if msg == "AI_CREDITS_EXCEEDED":
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="AI assistant is temporarily unavailable due to service limits. Please try again later.",
            )
        if msg == "AI_AUTH_FAILED":
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="AI service is temporarily misconfigured. Please contact support.",
            )
        if msg == "AI_TIMEOUT":
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="AI assistant timed out. Please try again.",
            )
        if msg == "AI_CONNECTION_ERROR":
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="AI service is temporarily unreachable. Please try again later.",
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
