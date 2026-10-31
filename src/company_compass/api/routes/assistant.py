"""Streaming transport for the single LangGraph conversation workflow."""

import asyncio
import json
import logging
from contextlib import aclosing

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from company_compass.api.dependencies import AssistantDependency
from company_compass.models.requests import ChatRequest

router = APIRouter(prefix="/api", tags=["assistant"])
logger = logging.getLogger(__name__)


@router.post("/chat/stream")
async def stream_chat(request: ChatRequest, assistant: AssistantDependency):
    async def events():
        try:
            async with aclosing(
                assistant.stream(
                    request.message, str(request.thread_id) if request.thread_id else None
                )
            ) as stream:
                async for event in stream:
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except asyncio.CancelledError:
            raise
        except Exception as error:
            logger.warning("Chat stream failed: %s", type(error).__name__)
            event = {"type": "error", "message": "The assistant could not finish. Please retry."}
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/chat")
async def chat(request: ChatRequest, assistant: AssistantDependency):
    """Collect the same workflow for scripts that do not consume SSE."""
    try:
        return await assistant.chat(
            request.message, str(request.thread_id) if request.thread_id else None
        )
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail="The assistant could not process this turn.",
        ) from None
