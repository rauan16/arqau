import pytest

from app.core.auth_rate_limit import _reset_all_limiters
from app.core.rate_limit import get_demo_ai_limiter, get_provider_limiter


@pytest.fixture(autouse=True)
def reset_rate_limiters():
    """Keep IP-based auth and demo-AI limits isolated between tests.

    The demo AI limiter is a process-wide singleton keyed by client IP, and the
    provider-call budget (Tier 1) is keyed by user id. Both are module-level
    singletons, so they must be reset before every test to prevent cross-test
    bucket accumulation (e.g. the 30 req/min demo ceiling or the 20/hour
    provider budget) from leaking between test modules.
    """
    _reset_all_limiters()
    get_demo_ai_limiter().reset()
    get_provider_limiter().reset()
