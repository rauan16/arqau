"""In-process IP-based rate limiter for authentication endpoints.

Single-instance MVP: no Redis, no distributed state, no background workers.
The limiter is per-process and resets on restart.

Three limiters:
- Login: 10 attempts per 15 minutes per IP
- Register: 5 attempts per hour per IP
- Refresh: 30 requests per 15 minutes per IP

Concurrency: the lock is held only during brief counter bookkeeping
and is released before any external call. Lazy cleanup of expired buckets
prevents unbounded memory growth.

This limiter is PER-PROCESS: counters reset when the process restarts
and are not shared across workers or instances.

CLIENT IP EXTRACTION:
In production behind Render's reverse proxy, the real client IP may be
in headers like X-Forwarded-For, X-Real-IP, or Fly-Client-IP. However,
Render does not document which header to trust, and spoofed headers
are a risk. This implementation uses request.client.host (the immediate
peer IP) as the safe default. In production behind a trusted proxy,
configure the proxy to set a trusted header and update get_client_ip().

This means all requests from the same proxy/load balancer will share
the same rate limit counter. For true per-client-IP limiting in a
multi-instance deployment, a Redis-backed distributed limiter is required.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Optional

from fastapi import Request, HTTPException, status


@dataclass
class _Bucket:
    count: int = 0
    window_start: float = field(default_factory=time.monotonic)


class RateLimiter:
    """In-process, per-IP sliding-window rate limiter.

    Keyed by client IP address. Uses a monotonic clock.
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

    async def try_acquire(self, key: str) -> bool:
        """Acquire one token for `key` (IP address). Returns True if allowed."""
        async with self._lock:
            now = self._clock()
            bucket = self._buckets.get(key)
            if bucket is None or self._is_expired(bucket, now):
                bucket = _Bucket(count=0, window_start=now)
                self._buckets[key] = bucket
            if bucket.count >= self._max_calls:
                return False
            bucket.count += 1
            if len(self._buckets) > _CLEANUP_THRESHOLD:
                self._sweep_expired(now)
            return True

    def remaining(self, key: str) -> int:
        """Remaining tokens for `key` within the current window."""
        now = self._clock()
        bucket = self._buckets.get(key)
        if bucket is None or self._is_expired(bucket, now):
            return self._max_calls
        return max(0, self._max_calls - bucket.count)

    def retry_after_seconds(self, key: str) -> float:
        """Seconds until the key's current window resets (for Retry-After)."""
        now = self._clock()
        bucket = self._buckets.get(key)
        if bucket is None or self._is_expired(bucket, now):
            return 0.0
        return max(0.0, self._window_seconds - (now - bucket.window_start))

    def _is_expired(self, bucket: _Bucket, now: float) -> bool:
        return (now - bucket.window_start) >= self._window_seconds

    def _sweep_expired(self, now: float) -> None:
        expired = [
            k for k, b in self._buckets.items()
            if self._is_expired(b, now)
        ]
        for k in expired:
            del self._buckets[k]

    def reset(self) -> None:
        """Clear all buckets. Test helper only."""
        self._buckets.clear()


# Configuration — development defaults, override via env/config later if needed
LOGIN_MAX_ATTEMPTS = 10
LOGIN_WINDOW_SECONDS = 15 * 60  # 15 minutes

REGISTER_MAX_ATTEMPTS = 5
REGISTER_WINDOW_SECONDS = 60 * 60  # 1 hour

REFRESH_MAX_ATTEMPTS = 30
REFRESH_WINDOW_SECONDS = 15 * 60  # 15 minutes

_CLEANUP_THRESHOLD = 1000  # sweep expired buckets when dict grows this large


# Module-level singletons — configured once per process
_LOGIN_LIMITER = RateLimiter(LOGIN_MAX_ATTEMPTS, LOGIN_WINDOW_SECONDS)
_REGISTER_LIMITER = RateLimiter(REGISTER_MAX_ATTEMPTS, REGISTER_WINDOW_SECONDS)
_REFRESH_LIMITER = RateLimiter(REFRESH_MAX_ATTEMPTS, REFRESH_WINDOW_SECONDS)


def get_login_limiter() -> RateLimiter:
    """Login rate limiter: 10 attempts per 15 minutes per IP."""
    return _LOGIN_LIMITER


def get_register_limiter() -> RateLimiter:
    """Register rate limiter: 5 attempts per hour per IP."""
    return _REGISTER_LIMITER


def get_refresh_limiter() -> RateLimiter:
    """Refresh rate limiter: 30 requests per 15 minutes per IP."""
    return _REFRESH_LIMITER


async def get_client_ip(request: Request) -> str:
    """
    Extract client IP address from request.

    SECURITY NOTE: In production behind Render's reverse proxy, the real
    client IP may be in headers like X-Forwarded-For, X-Real-IP, or
    Fly-Client-IP. However, Render does not document which header to trust,
    and spoofed headers are a risk. This implementation uses
    request.client.host (the immediate peer IP) as the safe default.

    LIMITATION: All requests from the same proxy/load balancer will share
    the same rate limit counter. For true per-client-IP limiting in a
    multi-instance deployment, a Redis-backed distributed limiter is required.

    If deploying behind a trusted proxy that sets a known header (e.g.,
    X-Forwarded-For with a known number of proxy hops), update this
    function to extract and trust that header.
    """
    # Safe default: immediate peer IP from the ASGI connection
    # This cannot be spoofed by the client
    client = request.client
    if client is not None:
        return client.host
    return "unknown"


async def enforce_login_rate_limit(request: Request) -> None:
    """Enforce login rate limit: 10 attempts per 15 minutes per IP."""
    from fastapi import HTTPException, status

    client_ip = await get_client_ip(request)
    limiter = get_login_limiter()
    if not await limiter.try_acquire(client_ip):
        retry_after = limiter.retry_after_seconds(client_ip)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Please try again later.",
            headers={"Retry-After": str(int(retry_after) + 1)},
        )


async def enforce_register_rate_limit(request: Request) -> None:
    """Enforce register rate limit: 5 attempts per hour per IP."""
    from fastapi import HTTPException, status

    client_ip = await get_client_ip(request)
    limiter = get_register_limiter()
    if not await limiter.try_acquire(client_ip):
        retry_after = limiter.retry_after_seconds(client_ip)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many registration attempts. Please try again later.",
            headers={"Retry-After": str(int(retry_after) + 1)},
        )


async def enforce_refresh_rate_limit(request: Request) -> None:
    """Enforce refresh rate limit: 30 requests per 15 minutes per IP."""
    from fastapi import HTTPException, status

    client_ip = await get_client_ip(request)
    limiter = get_refresh_limiter()
    if not await limiter.try_acquire(client_ip):
        retry_after = limiter.retry_after_seconds(client_ip)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many refresh requests. Please try again later.",
            headers={"Retry-After": str(int(retry_after) + 1)},
        )


# Test helper: reset all limiters
def _reset_all_limiters() -> None:
    """Reset all rate limiters. Test helper only."""
    _LOGIN_LIMITER.reset()
    _REGISTER_LIMITER.reset()
    _REFRESH_LIMITER.reset()