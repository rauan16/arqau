"""Legacy AI schemas.

`ChatRequest` is retained (including the optional `conversation_id`) so existing
clients keep working with POST /ai/chat.

`ChatResponse` is re-exported from the Phase 3.4 copilot schema so the historical
import path `from app.schemas.ai import ChatResponse` continues to resolve. The
copilot response is a superset of the legacy shape: it still exposes `response`
and `disclaimer`, and adds structured key facts, server-assembled authoritative
facts, data limitations, suggested questions, and AI metadata.

The legacy `WithdrawalAnalysis` schema was removed in Phase 3.4. Its fields
(`risk_level`, `recommendation`, `reserve_status`, `covered_expenses`, and
LLM-supplied balances) encoded exactly the AI-side financial calculation that
the Phase 3 architecture prohibits. POST /ai/analyze-withdrawal now delegates to
the authoritative Phase 3.2 analysis plus the Phase 3.3 structured decision.
"""

from __future__ import annotations

from typing import Annotated, Optional

from pydantic import BaseModel, StringConstraints

from app.schemas.ai_copilot import CopilotResponse

# Bound the untrusted user message before it reaches the provider or a prompt.
MAX_MESSAGE_CHARS = 2000
MAX_CONVERSATION_ID_CHARS = 128

BoundedMessage = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, min_length=1, max_length=MAX_MESSAGE_CHARS
    ),
]
BoundedConversationId = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, min_length=1, max_length=MAX_CONVERSATION_ID_CHARS
    ),
]


class ChatRequest(BaseModel):
    """Input for POST /ai/chat.

    `conversation_id` is optional metadata only. This repository contains no
    conversation persistence, so no history is stored and none is implied.
    """

    message: BoundedMessage
    conversation_id: Optional[BoundedConversationId] = None


# Legacy alias: `from app.schemas.ai import ChatResponse` keeps resolving to the
# Phase 3.4 copilot envelope, which is a superset of the legacy shape.
ChatResponse = CopilotResponse

__all__ = ["ChatRequest", "ChatResponse"]