"""Shared AI safety helpers for the ARQAU financial intelligence layer.

Phase 3.4 removed the legacy AI implementation that used to live in this
module. What it used to contain — and what is now deliberately gone:

- eager module-level construction of an OpenAI client (which made importing
  `app.main` fail whenever no API key was configured),
- hand-built prompts that interpolated the raw user message into a single
  "system-like" prompt,
- AI-side calculation of balances, expense coverage, reserve status, risk
  level, and recommendations,
- AI-side fallback arithmetic that patched authoritative numbers back into
  model output.

All of that is prohibited by the Phase 3 architecture: the backend is
authoritative for financial values and the LLM may only explain them.

What remains is the provider-diagnostic logging shared by the Phase 3.3
decision layer and the Phase 3.4 copilot layer. It exists so secrets are
never written to logs by either layer, and so no OpenAI client is constructed
at import time.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Optional

logger = logging.getLogger("arqau.ai")

# Anything that could carry a credential is redacted before it reaches a log
# record. Error strings from SDKs can embed request headers or response bodies.
_SECRET_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"(?i)(sk-or-[A-Za-z0-9_\-]+)", "[REDACTED_KEY]"),
    (r"(?i)(sk-[A-Za-z0-9_\-]+)", "[REDACTED_KEY]"),
    (r"(?i)(authorization[\"'\s:=]+)[^\s,}}\"]+", r"\1[REDACTED]"),
    (r"(?i)(api[_-]?key[\"'\s:=]+)[^\s,}}\"]+", r"\1[REDACTED]"),
    (r"(?i)(bearer\s+)[A-Za-z0-9._\-]+", r"\1[REDACTED]"),
    (r"(?i)(refresh_token[\"'\s:=]+)[^\s,}}\"]+", r"\1[REDACTED]"),
    (r"(?i)(password[\"'\s:=]+)[^\s,}}\"]+", r"\1[REDACTED]"),
)

_COMPILED_SECRET_PATTERNS = tuple(
    (re.compile(pattern), replacement) for pattern, replacement in _SECRET_PATTERNS
)

_MAX_LOGGED_BODY = 500
_MAX_LOGGED_MESSAGE = 300


def scrub_secrets(text: Optional[str]) -> str:
    """Redact anything that could be an API key or auth token."""
    if not text:
        return ""
    for pattern, replacement in _COMPILED_SECRET_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def log_provider_error(
    context: str,
    exc: BaseException,
    *,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    extra: Optional[dict[str, Any]] = None,
) -> None:
    """Log an AI provider failure without leaking credentials.

    Only the exception type name, a scrubbed/truncated message, and non-secret
    diagnostics are recorded. The API key is never passed in or logged.
    """
    safe_extra = {
        key: value for key, value in (extra or {}).items() if "key" not in key.lower()
    }
    logger.warning(
        "AI request failed: context=%s provider=%s model=%s error_type=%s error=%s extra=%s",
        context,
        provider,
        model,
        type(exc).__name__,
        scrub_secrets(str(exc))[:_MAX_LOGGED_MESSAGE],
        safe_extra,
    )


def log_provider_diagnostic(
    context: str,
    exc: BaseException,
    *,
    provider: Optional[str] = None,
    model: Optional[str] = None,
) -> None:
    """Log safe provider diagnostics: status code, model, scrubbed response body.

    Never logs the API key or an Authorization header value.
    """
    body = ""
    try:
        raw = getattr(exc, "response", None)
        if raw is not None:
            body = getattr(raw, "text", "") or ""
    except Exception:  # noqa: BLE001 - diagnostics must never raise
        body = ""
    logger.error(
        "PROVIDER_DIAG context=%s provider=%s model=%s http_status=%s response_body=%s",
        context,
        provider,
        model,
        getattr(exc, "status_code", None),
        scrub_secrets(body)[:_MAX_LOGGED_BODY],
    )