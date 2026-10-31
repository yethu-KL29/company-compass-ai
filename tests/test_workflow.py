"""Compaction preserves complete turns and keeps internal summaries private."""

import pytest
from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage, ToolMessage
from test_agent import ScriptedModel, available_tools, settings, tool_chunk

from company_compass.agents.assistant import Assistant
from company_compass.agents.memory import compaction_boundary


def test_compaction_boundary_keeps_tool_call_result_pairs_together():
    messages = [
        HumanMessage(content="first", id="1"),
        AIMessage(
            content="", id="2", tool_calls=[{"id": "tool", "name": "company_rag", "args": {}}]
        ),
        ToolMessage(content="evidence", tool_call_id="tool", id="3"),
        AIMessage(content="answer", id="4"),
        HumanMessage(content="second", id="5"),
    ]
    assert compaction_boundary(messages, keep_messages=3) == 4


@pytest.mark.asyncio
async def test_compaction_uses_summary_and_retains_recent_complete_turn():
    model = ScriptedModel(
        [
            [AIMessageChunk(content="Old answer " * 50)],
            [AIMessageChunk(content="New answer")],
        ]
    )
    assistant = Assistant(
        settings(memory_token_limit=80, memory_keep_messages=1), model, available_tools([])
    )
    first = await assistant.chat("API for ten users under INR10000/month " * 10)
    events = [
        event async for event in assistant.stream("Compare those choices", first["thread_id"])
    ]
    assert len(model.summaries) == 1
    assert "API" in str(model.summaries[0])
    assert "Team needs API and ten users" in str(model.inputs[-1])
    assert [item.content for item in model.inputs[-1] if isinstance(item, HumanMessage)] == [
        "Compare those choices"
    ]
    assert "Team needs API" not in "".join(event.get("text", "") for event in events)
    state = await assistant.workflow.aget_state({"configurable": {"thread_id": first["thread_id"]}})
    assert len(state.values["messages"]) == 2


@pytest.mark.asyncio
async def test_tool_loop_is_bounded_and_next_turn_is_coherent():
    class EndlessModel(ScriptedModel):
        async def astream(self, messages):
            yield tool_chunk("company_rag", {"query": "again"}, f"call-{len(messages)}")

    model = EndlessModel([])
    assistant = Assistant(settings(agent_recursion_limit=5), model, available_tools([]))
    with pytest.raises(Exception, match="limit|steps|recursion"):
        await assistant.chat("Keep looking", "bounded-thread")
    state = await assistant.workflow.aget_state({"configurable": {"thread_id": "bounded-thread"}})
    assert not state.values.get("messages")


@pytest.mark.asyncio
async def test_same_thread_turns_are_serialized():
    import asyncio

    model = ScriptedModel(
        [
            [AIMessageChunk(content="first answer")],
            [AIMessageChunk(content="second answer")],
        ]
    )
    assistant = Assistant(settings(), model, available_tools([]))
    await asyncio.gather(assistant.chat("first", "shared"), assistant.chat("second", "shared"))
    state = await assistant.workflow.aget_state({"configurable": {"thread_id": "shared"}})
    assert [item.content for item in state.values["messages"]] == [
        "first",
        "first answer",
        "second",
        "second answer",
    ]


@pytest.mark.asyncio
async def test_cancelled_stream_restores_prior_completed_turn():
    model = ScriptedModel(
        [
            [AIMessageChunk(content="Remembered")],
            [tool_chunk("company_rag", {"query": "policy"}, "cancelled-call")],
            [AIMessageChunk(content="Interrupted answer")],
            [AIMessageChunk(content="Recovered answer")],
        ]
    )
    assistant = Assistant(settings(), model, available_tools([]))
    first = await assistant.chat("My team has ten people")
    stream = assistant.stream("Tell me the policy", first["thread_id"])
    async for event in stream:
        if event["type"] == "token":
            break
    await stream.aclose()
    await assistant.chat("How many people?", first["thread_id"])
    assert [item.content for item in model.inputs[-1] if isinstance(item, HumanMessage)] == [
        "My team has ten people",
        "How many people?",
    ]
    assert not any(isinstance(item, ToolMessage) for item in model.inputs[-1])


@pytest.mark.asyncio
async def test_provider_reasoning_blocks_are_not_sent_to_user():
    model = ScriptedModel(
        [
            [
                AIMessageChunk(
                    content=[
                        {"type": "reasoning", "text": "Internal reasoning"},
                        {"type": "text", "text": "Private thought", "thought": True},
                        {"type": "text", "text": "Public answer"},
                    ]
                )
            ]
        ]
    )
    events = [
        event async for event in Assistant(settings(), model, available_tools([])).stream("Hi")
    ]
    assert "".join(event.get("text", "") for event in events) == "Public answer"
    assert events[-1]["answer"] == "Public answer"


@pytest.mark.asyncio
async def test_cancellation_closes_inflight_model_before_restoring_memory():
    import asyncio

    closed = asyncio.Event()

    class WaitingModel(ScriptedModel):
        async def astream(self, messages):
            try:
                yield AIMessageChunk(content="Partial")
                await asyncio.Event().wait()
            finally:
                closed.set()

    assistant = Assistant(settings(), WaitingModel([]), available_tools([]))
    stream = assistant.stream("Hi", "cancel-inflight")
    await anext(stream)
    await anext(stream)
    await stream.aclose()
    assert closed.is_set()


@pytest.mark.asyncio
async def test_completed_turns_do_not_retain_historical_checkpoints():
    model = ScriptedModel([[AIMessageChunk(content="Answer")] for _ in range(4)])
    assistant = Assistant(settings(), model, available_tools([]))
    for _ in range(4):
        await assistant.chat("Hello", "latest-only")
    config = {"configurable": {"thread_id": "latest-only"}}
    checkpoints = [snapshot async for snapshot in assistant.workflow.aget_state_history(config)]
    assert len(checkpoints) <= 2
    assert len(checkpoints[0].values["messages"]) == 8


@pytest.mark.asyncio
@pytest.mark.parametrize("summary", ["", " \n\t "])
async def test_empty_compaction_summary_rolls_back_without_losing_requirements(summary):
    class EmptySummaryModel(ScriptedModel):
        async def ainvoke(self, messages):
            return AIMessage(content=summary)

    model = EmptySummaryModel([[AIMessageChunk(content="Remembered " * 50)]])
    assistant = Assistant(
        settings(memory_token_limit=80, memory_keep_messages=1), model, available_tools([])
    )
    first = await assistant.chat("Mandatory API, ten users, INR10000/month " * 10)
    config = {"configurable": {"thread_id": first["thread_id"]}}
    before = await assistant.workflow.aget_state(config)
    with pytest.raises(ValueError, match="summary.*empty|empty.*summary"):
        await assistant.chat("Compare those choices", first["thread_id"])
    after = await assistant.workflow.aget_state(config)
    assert after.values == before.values


@pytest.mark.asyncio
async def test_cancelled_anyio_scope_cannot_interrupt_memory_replacement(monkeypatch):
    import anyio

    model = ScriptedModel([[AIMessageChunk(content="Remembered")]])
    assistant = Assistant(settings(), model, available_tools([]))
    first = await assistant.chat("My team has ten people")
    config = {"configurable": {"thread_id": first["thread_id"]}}
    before = await assistant.workflow.aget_state(config)
    update_state = assistant.workflow.aupdate_state

    async def checkpoint_before_update(*args, **kwargs):
        await anyio.lowlevel.checkpoint()
        return await update_state(*args, **kwargs)

    monkeypatch.setattr(assistant.workflow, "aupdate_state", checkpoint_before_update)
    with anyio.CancelScope() as scope:
        scope.cancel()
        await assistant._replace_memory(first["thread_id"], config, before.values)
    after = await assistant.workflow.aget_state(config)
    assert after.values == before.values


@pytest.mark.asyncio
async def test_summary_serializes_tool_transcript_as_data_without_native_tool_messages():
    from company_compass.agents.memory import compact_messages

    class SummaryModel(ScriptedModel):
        async def ainvoke(self, messages):
            assert all(not isinstance(item, ToolMessage) for item in messages)
            assert all(not getattr(item, "tool_calls", []) for item in messages)
            assert isinstance(messages[-1], HumanMessage)
            assert "prior requirement" in messages[-1].content
            assert "company_rag" in messages[-1].content
            assert "supported evidence" in messages[-1].content
            assert "prior requirement" not in messages[0].content
            return AIMessage(content="Preserved requirements and evidence")

    messages = [
        HumanMessage(content="Need ten users", id="1"),
        AIMessage(
            content="",
            id="2",
            tool_calls=[{"id": "call", "name": "company_rag", "args": {"query": "policy"}}],
        ),
        ToolMessage(content="supported evidence " * 50, tool_call_id="call", id="3"),
        AIMessage(content="Previous answer", id="4"),
        HumanMessage(content="Follow up", id="5"),
    ]
    result = await compact_messages(
        {"messages": messages, "summary": "prior requirement"}, SummaryModel([]), 80, 1
    )
    assert result["summary"] == "Preserved requirements and evidence"
