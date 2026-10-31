"""Thread ownership and public streaming events around the LangGraph workflow."""

import asyncio
import json
from contextlib import aclosing
from pathlib import Path
from uuid import uuid4

from anyio import CancelScope
from langchain_core.messages import HumanMessage, ToolMessage

from company_compass.agents.memory import message_text
from company_compass.agents.workflow import build_workflow
from company_compass.core.settings import ROOT
from company_compass.integrations.observability import TraceTurn


def _evidence(messages):
    sources, warnings = [], []
    for message in messages:
        if not isinstance(message, ToolMessage):
            continue
        evidence = message.artifact
        if not isinstance(evidence, dict):
            try:
                evidence = json.loads(message.content)
            except (ValueError, TypeError):
                continue
        if isinstance(evidence, dict):
            sources.extend(evidence.get("sources", []))
            warnings.extend(evidence.get("warnings", []))
    unique = {source.get("document_id", source.get("url", "")): source for source in sources}
    return list(unique.values()), list(dict.fromkeys(warnings))


class Assistant:
    def __init__(self, settings, model, tools, telemetry=None):
        self.settings = settings
        self._locks: dict[str, asyncio.Lock] = {}
        self.workflow = None
        self.telemetry = telemetry
        if model is not None:
            prompt = Path(__file__).with_name("system_prompt.md").read_text(encoding="utf-8")
            schema = (ROOT / "docs/knowledge/catalog/schema.md").read_text(encoding="utf-8")
            self.workflow = build_workflow(model, tools, prompt + "\n\n" + schema, settings)

    async def _replace_memory(self, thread_id, config, values):
        """Keep only the latest state; discarded transcripts need no time-travel copies."""
        # ASGI disconnects cancel the surrounding AnyIO scope at every await.
        # Delete and restore must finish together before that cancellation resumes.
        with CancelScope(shield=True):
            await self.workflow.checkpointer.adelete_thread(thread_id)
            if values:
                await self.workflow.aupdate_state(config, values, as_node="agent")

    async def stream(self, message: str, thread_id: str | None = None):
        if self.workflow is None:
            raise ValueError("Configure Gemini before using the assistant")
        thread_id = thread_id or str(uuid4())
        config = {
            "configurable": {"thread_id": thread_id},
            "recursion_limit": self.settings.agent_recursion_limit,
        }
        lock = self._locks.setdefault(thread_id, asyncio.Lock())
        async with lock:
            before = await self.workflow.aget_state(config)
            turn = self.telemetry.start_turn(thread_id, message) if self.telemetry else TraceTurn()
            completed = False
            try:
                yield {"type": "session", "thread_id": thread_id}
                async with aclosing(
                    self.workflow.astream(
                        {"messages": [HumanMessage(content=message)]},
                        {**config, **turn.config},
                        stream_mode="custom",
                    )
                ) as events:
                    async for event in events:
                        yield event
                state = await self.workflow.aget_state(config)
                messages = state.values["messages"]
                start = max(
                    index for index, item in enumerate(messages) if isinstance(item, HumanMessage)
                )
                sources, warnings = _evidence(messages[start:])
                await self._replace_memory(thread_id, config, state.values)
                completed = True
                answer = message_text(messages[-1])
                turn.finish(answer=answer)
                yield {
                    "type": "done",
                    "thread_id": thread_id,
                    "answer": answer,
                    "sources": sources,
                    "warnings": warnings,
                    **({"trace_id": turn.trace_id} if turn.trace_id else {}),
                }
            except (asyncio.CancelledError, GeneratorExit):
                turn.finish(status="cancelled")
                raise
            except Exception as error:
                turn.finish(status="error", error_type=type(error).__name__)
                raise
            finally:
                if not completed:
                    # A failed/cancelled turn must not leave unmatched tool calls in history.
                    await self._replace_memory(thread_id, config, before.values)

    async def chat(self, message: str, thread_id: str | None = None) -> dict:
        async for event in self.stream(message, thread_id):
            if event["type"] == "done":
                return {key: value for key, value in event.items() if key != "type"}
        raise ValueError("The assistant did not complete its response")
