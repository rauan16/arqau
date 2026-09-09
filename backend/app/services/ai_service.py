import json
from openai import OpenAI, RateLimitError, APIStatusError
from app.config import get_settings

settings = get_settings()

client = OpenAI(api_key=settings.openai_api_key)


def build_withdrawal_prompt(ctx: dict) -> str:
    has_data = any([
        ctx.get("earned_amount", 0) > 0,
        ctx.get("total_income", 0) > 0,
        ctx.get("total_expenses", 0) > 0,
    ])
    empty_profile_warning = ""
    if not has_data:
        empty_profile_warning = """
IMPORTANT: The user has no financial data yet (no earned wages, no income, no expenses recorded).
You MUST NOT invent any figures. In your response, state that you don't have enough data to give a personalized recommendation and ask the user to set their earned wages, record income/expenses, and share their payday date.
"""

    return f"""You are a financial assistant for ARQAU, an earned wage access app. You must ONLY interpret the provided financial context. Do NOT invent, estimate, or guess any financial figures (salary, balance, earned wages, transactions, expenses, debts, future income, or guarantees).

Financial context:
- Earned this period: {ctx.get('earned_amount', 0):,} ₸
- Already accessed: {ctx.get('accessed_amount', 0):,} ₸
- Available now: {ctx.get('available_amount', 0):,} ₸
- Withdrawal amount: {ctx.get('withdrawal_amount', 0):,} ₸
- Total income: {ctx.get('total_income', 0):,} ₸
- Total expenses: {ctx.get('total_expenses', 0):,} ₸
- Net balance: {ctx.get('net_balance', 0):,} ₸
{empty_profile_warning}
Rules:
1. Base your analysis ONLY on the numbers above.
2. Determine risk_level as low/medium/high based on whether the withdrawal leaves the user with enough for upcoming obligations relative to available amount.
3. recommendation must be one of: proceed, caution, reconsider.
4. reserve_status should describe whether the remaining amount covers a basic reserve.
5. explanation should be 1-2 sentences referencing the actual numbers.
6. disclaimer must state: "This is illustrative guidance, not financial advice. ARQAU does not guarantee any specific financial outcome."

Return ONLY valid JSON with keys: risk_level, recommendation, reserve_status, explanation, disclaimer, remaining_amount, covered_expenses (boolean), total_income, total_expenses, net_balance, withdrawal_amount, earned_amount, accessed_amount, available_amount."""


def build_chat_prompt(message: str, ctx: dict) -> str:
    has_data = any([
        ctx.get("earned_amount", 0) > 0,
        ctx.get("total_income", 0) > 0,
        ctx.get("total_expenses", 0) > 0,
    ])
    empty_profile_warning = ""
    if not has_data:
        empty_profile_warning = """
IMPORTANT: The user has no financial data yet (no earned wages, no income, no expenses recorded).
You MUST NOT invent any figures. Tell the user you don't have enough data yet and ask them to:
1. Set their earned wages
2. Record their income and upcoming expenses
3. Share their payday date
"""

    return f"""You are a financial assistant for ARQAU. You must ONLY interpret the provided financial context. Do NOT invent, estimate, or guess any financial figures.

Financial context:
- Earned this period: {ctx.get('earned_amount', 0):,} ₸
- Already accessed: {ctx.get('accessed_amount', 0):,} ₸
- Available now: {ctx.get('available_amount', 0):,} ₸
- Total income: {ctx.get('total_income', 0):,} ₸
- Total expenses: {ctx.get('total_expenses', 0):,} ₸
- Net balance: {ctx.get('net_balance', 0):,} ₸
{empty_profile_warning}
User message: {message}

Rules:
1. Answer using ONLY the financial context above.
2. If asked about amounts not in context, say you don't have that data yet.
3. Be concise and helpful.
4. Do NOT provide financial guarantees or promise specific outcomes.
5. End with: "This is illustrative guidance, not financial advice."

Return ONLY valid JSON with keys: response, disclaimer."""


async def analyze_withdrawal(ctx: dict) -> dict:
    prompt = build_withdrawal_prompt(ctx)
    try:
        completion = client.chat.completions.create(
            model=settings.openai_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=500,
        )
        content = completion.choices[0].message.content.strip()
        if content.startswith("```"):
            content = content.strip("`")
            if content.startswith("json"):
                content = content[4:].strip()
        result = json.loads(content)
        result.setdefault("remaining_amount", ctx.get("available_amount", 0) - ctx.get("withdrawal_amount", 0))
        result.setdefault("withdrawal_amount", ctx.get("withdrawal_amount", 0))
        result.setdefault("earned_amount", ctx.get("earned_amount", 0))
        result.setdefault("accessed_amount", ctx.get("accessed_amount", 0))
        result.setdefault("available_amount", ctx.get("available_amount", 0))
        result.setdefault("total_income", ctx.get("total_income", 0))
        result.setdefault("total_expenses", ctx.get("total_expenses", 0))
        result.setdefault("net_balance", ctx.get("net_balance", 0))
        return result
    except RateLimitError:
        raise RuntimeError("AI_QUOTA_EXCEEDED")
    except APIStatusError as e:
        if e.status_code == 429 or "quota" in str(e).lower():
            raise RuntimeError("AI_QUOTA_EXCEEDED")
        raise RuntimeError(f"OpenAI error: {str(e)}")
    except Exception as e:
        raise RuntimeError(f"OpenAI error: {str(e)}")


async def chat_with_user(message: str, ctx: dict) -> dict:
    prompt = build_chat_prompt(message, ctx)
    try:
        completion = client.chat.completions.create(
            model=settings.openai_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5,
            max_tokens=400,
        )
        content = completion.choices[0].message.content.strip()
        if content.startswith("```"):
            content = content.strip("`")
            if content.startswith("json"):
                content = content[4:].strip()
        result = json.loads(content)
        result.setdefault("disclaimer", "This is illustrative guidance, not financial advice. ARQAU does not guarantee any specific financial outcome.")
        return result
    except RateLimitError:
        raise RuntimeError("AI_QUOTA_EXCEEDED")
    except APIStatusError as e:
        if e.status_code == 429 or "quota" in str(e).lower():
            raise RuntimeError("AI_QUOTA_EXCEEDED")
        raise RuntimeError(f"OpenAI error: {str(e)}")
    except Exception as e:
        raise RuntimeError(f"OpenAI error: {str(e)}")
