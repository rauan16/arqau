"""In-process per-user AI rate limiter (Phase 3.5.2A).

Single-instance MVP: no Redis, no distributed state, no background workers.
The limiter is per-process and resets on restart.

Two tiers:
  Tier 1 — provider-call budget: N attempts per user per rolling hour.
           Consumed only when an external provider call is imminent.
  Tier 2 — total-request ceiling: N requests per user per rolling minute.
           Enforced at route entry; returns HTTP 429 when exceeded.

Concurrency: the lock is held only during brief counter bookkeeping
and is released before any external call. Lazy cleanup of expired buckets
prevents unbounded memory growth.

This limiter is PER-PROCESS: counters reset when the process restarts
and are not shared across workers or instances.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Optional

from fastapi import HTTPException, Request, status

from app.core.auth_rate_limit import get_client_ip

# Configuration — editable via env/config later if needed
PROVIDER_CALLS_PER_WINDOW = 20
PROVIDER_WINDOW_SECONDS = 60 * 60  # 60 minutes

TOTAL_REQUESTS_PER_WINDOW = 120
TOTAL_WINDOW_SECONDS = 60  # 60 seconds

_CLEANUP_THRESHOLD = 1000  # sweep expired buckets when dict grows this large


@dataclass
class _Bucket:
    count: int = 0
    window_start: float = field(default_factory=time.monotonic)


class RateLimiter:
    """In-process, per-user sliding-window rate limiter.

    Keyed by authenticated user identity (never IP). Uses a monotonic clock.
    Concurrency-safe: the lock is held only during brief counter bookkeeping
    and is released before any external call. Lazy cleanup of expired buckets
    prevents unbounded memory growth.

    This limiter is PER-PROCESS: counters reset when the process restarts
    and are not shared across workers or instances.
    """

    def __init__(
        self,
        max_calls: int,
        window_seconds: float,
        clock: callable = time.monotonic,
    ) -> None:
        if max_calls <= 0:
            raise ValueError("max_calls must be positive")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be positive")
        self._max_calls = max_calls
        self._window_seconds = window_seconds
        self._clock = clock
        self._buckets: dict[str, _Bucket] = {}
        self._lock = asyncio.Lock()

    async def try_acquire(self, user_id: str) -> bool:
        """Acquire one token for `user_id`. Returns True if allowed."""
        async with self._lock:
            now = self._clock()
            bucket = self._buckets.get(user_id)
            if bucket is None or self._is_expired(bucket, now):
                bucket = _Bucket(count=0, window_start=now)
                self._buckets[user_id] = bucket
            if bucket.count >= self._max_calls:
                return False
            bucket.count += 1
            if len(self._buckets) > _CLEANUP_THRESHOLD:
                self._sweep_expired(now)
            return True

    def remaining(self, user_id: str) -> int:
        """Remaining tokens for `user_id` within the current window."""
        now = self._clock()
        bucket = self._buckets.get(user_id)
        if bucket is None or self._is_expired(bucket, now):
            return self._max_calls
        return max(0, self._max_calls - bucket.count)

    def retry_after_seconds(self, user_id: str) -> float:
        """Seconds until the user's current window resets (for Retry-After)."""
        now = self._clock()
        bucket = self._buckets.get(user_id)
        if bucket is None or self._is_expired(bucket, now):
            return 0.0
        return max(0.0, self._window_seconds - (now - bucket.window_start))

    def _is_expired(self, bucket: _Bucket, now: float) -> bool:
        return (now - bucket.window_start) >= self._window_seconds

    def _sweep_expired(self, now: float) -> None:
        expired = [
            uid for uid, b in self._buckets.items()
            if self._is_expired(b, now)
        ]
        for uid in expired:
            del self._buckets[uid]

    def reset(self) -> None:
        """Clear all buckets. Test helper only."""
        self._buckets.clear()


# Module-level singletons — configured once per process
_PROVIDER_LIMITER = RateLimiter(PROVIDER_CALLS_PER_WINDOW, PROVIDER_WINDOW_SECONDS)
_TOTAL_LIMITER = RateLimiter(TOTAL_REQUESTS_PER_WINDOW, TOTAL_WINDOW_SECONDS)


def get_provider_limiter() -> RateLimiter:
    """Tier 1: provider-call budget (20/60min)."""
    return _PROVIDER_LIMITER


def get_total_limiter() -> RateLimiter:
    """Tier 2: total AI request ceiling (120/60s)."""
    return _TOTAL_LIMITER


class RateLimitExceeded(Exception):
    """Raised when the total AI request ceiling is exceeded."""
    def __init__(self, retry_after: float) -> None:
        self.retry_after = retry_after
        super().__init__("AI request ceiling exceeded")


async def enforce_total_ceiling(user_id: str) -> None:
    """Enforce the total AI request ceiling (Tier 2).
    
    Raises HTTPException with 429 and Retry-After if exceeded.
    """
    from fastapi import HTTPException, status
    
    if not await get_total_limiter().try_acquire(user_id):
        retry_after = get_total_limiter().retry_after_seconds(user_id)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests",
            headers={"Retry-After": str(int(retry_after) + 1)},
        )


# ---------------------------------------------------------------------------
# Demo AI public endpoint rate limiting (Phase 3.5.2C).
#
# Public POST /demo/ai/chat has no authenticated user, so it is keyed by client
# IP instead of user identity. This is a single-instance, in-process limiter:
# counters reset on restart and are not shared across workers/instances. When
# TRUSTED_PROXY_COUNT is 0 (the safe default), every client behind the same
# reverse proxy shares one bucket — the IP cannot be spoofed, but per-client
# granularity is lost in multi-proxy deployments. A Redis-backed distributed
# limiter is required for true per-client-IP limiting at scale.
#
# IP extraction reuses the safe logic from app.core.auth_rate_limit:
#   - TRUSTED_PROXY_COUNT == 0: request.client.host (immediate peer, not
#     spoofable by the client).
#   - TRUSTED_PROXY_COUNT > 0: X-Forwarded-For at the trusted boundary, only
#     when the immediate peer is a verified trusted proxy operated by us.
# Never trust X-Forwarded-For from untrusted clients.
# ---------------------------------------------------------------------------

DEMO_AI_MAX_REQUESTS = 30
DEMO_AI_WINDOW_SECONDS = 60  # 1 minute

_DEMO_AI_LIMITER = RateLimiter(DEMO_AI_MAX_REQUESTS, DEMO_AI_WINDOW_SECONDS)


def get_demo_ai_limiter() -> RateLimiter:
    """IP-based rate limiter for public /demo/ai/chat (30 requests/min per IP)."""
    return _DEMO_AI_LIMITER


async def enforce_demo_ai_rate_limit(request: Request) -> None:
    """Enforce IP-based rate limit for the public demo AI chat.

    Raises HTTP 429 with Retry-After when the per-IP ceiling is exceeded.
    Checked before any provider call, so the LLM budget is never consumed by
    a rate-limited request.
    """
    client_ip = await get_client_ip(request)
    limiter = get_demo_ai_limiter()
    if not await limiter.try_acquire(client_ip):
        retry_after = limiter.retry_after_seconds(client_ip)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many demo AI requests. Please try again later.",
            headers={"Retry-After": str(int(retry_after) + 1)},
        )
