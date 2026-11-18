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
In production behind a reverse proxy (e.g., Render), the real client IP may be
in headers like X-Forwarded-For, X-Real-IP, or Fly-Client-IP. However,
forwarded headers can be spoofed by untrusted clients.

This implementation uses request.client.host (the immediate peer IP) as the
SAFE DEFAULT. This cannot be spoofed by the client.

When TRUSTED_PROXY_COUNT > 0 is explicitly configured, the implementation
parses X-Forwarded-For and uses the IP at position [-TRUSTED_PROXY_COUNT],
which corresponds to the client IP before the trusted proxy chain.
This is only safe when the immediate peer (request.client.host) is a verified
trusted proxy that the application operator controls.

LIMITATION: All requests from the same proxy/load balancer will share
the same rate limit counter when TRUSTED_PROXY_COUNT is 0.
For true per-client-IP limiting in a multi-instance deployment,
a Redis-backed distributed limiter is required.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Optional

from fastapi import Request, HTTPException, status

from app.config import get_settings


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

    SECURITY MODEL:
    - Default (TRUSTED_PROXY_COUNT = 0): Use request.client.host (immediate peer).
      This is the ONLY safe option when the proxy chain is not verified.
      All clients behind the same proxy share one rate-limit bucket.

    - TRUSTED_PROXY_COUNT > 0: Parse X-Forwarded-For and use the IP at
      position [-TRUSTED_PROXY_COUNT]. This is ONLY safe when:
        1. The immediate peer (request.client.host) is a trusted proxy
           that the operator controls and that correctly appends to
           X-Forwarded-For.
        2. The number of proxy hops is known and constant.

    NEVER trust X-Forwarded-For from untrusted clients. This function
    only reads X-Forwarded-For when TRUSTED_PROXY_COUNT > 0 AND the
    immediate peer is assumed to be a trusted proxy (operator responsibility).

    If the header is missing, malformed, or contains invalid IPs,
    fall back to request.client.host.

    For true per-client-IP limiting in a multi-instance deployment,
    a Redis-backed distributed limiter is required.
    """
    settings = get_settings()
    trusted_hops = settings.trusted_proxy_count

    # Safe default: immediate peer IP from the ASGI connection
    # This cannot be spoofed by the client
    client = request.client
    immediate_peer = client.host if client is not None else "unknown"

    # Only use forwarded headers when explicitly configured with trusted proxies
    if trusted_hops > 0:
        xff = request.headers.get("X-Forwarded-For")
        if xff:
            # X-Forwarded-For format: "client, proxy1, proxy2, ..."
            # The leftmost is the original client, rightmost is the last proxy before the app.
            # Each trusted proxy appends the previous hop's IP.
            # With N trusted proxies, X-Forwarded-For contains N IPs.
            # The client IP is at index [-trusted_hops] (e.g., -1 for 1 proxy, -2 for 2 proxies).
            ips = [ip.strip() for ip in xff.split(",") if ip.strip()]
            if len(ips) == trusted_hops:
                # Exact match: number of IPs equals trusted hop count
                candidate = ips[-trusted_hops]
                if _is_valid_ip(candidate):
                    return candidate
            elif len(ips) > trusted_hops:
                # More IPs than expected hops - could be additional untrusted proxies.
                # Use the IP at the trusted boundary, but log a warning in production.
                candidate = ips[-trusted_hops]
                if _is_valid_ip(candidate):
                    return candidate

    # Fallback to immediate peer (safe default)
    return immediate_peer


def _is_valid_ip(ip: str) -> bool:
    """Basic IP address validation (IPv4 and IPv6)."""
    # Reject empty or obviously invalid
    if not ip or len(ip) > 45:  # Max IPv6 length
        return False

    # Basic IPv4 check
    if "." in ip and ":" not in ip:
        parts = ip.split(".")
        if len(parts) != 4:
            return False
        try:
            return all(0 <= int(p) <= 255 for p in parts)
        except ValueError:
            return False

    # Basic IPv6 check (simplified - just check format)
    if ":" in ip:
        # Allow IPv6 including compressed formats
        # Full validation would use ipaddress module, but this is a fast path
        try:
            import ipaddress
            ipaddress.ip_address(ip)
            return True
        except ValueError:
            return False

    return False


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