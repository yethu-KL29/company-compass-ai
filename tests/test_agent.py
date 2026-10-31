"""Single-agent tool choice, streaming and thread memory regressions."""

import asyncio
import json
from types import SimpleNamespace

import pytest
from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage, ToolMessage
from langchain_core.tools import tool

from company_compass.agents.assistant import Assistant


class ScriptedModel:
    def __init__(self, rounds):
        self.rounds = list(rounds)
        self.inputs = []
        self.bound = []
        self.summaries = []

    def bind_tools(self, tools):
        self.bound = [item.name for item in tools]
        return self

    async def astream(self, messages):
        self.inputs.append(messages)
        for chunk in self.rounds.pop(0):
            await asyncio.sleep(0)
            yield chunk

    async def ainvoke(self, messages):
        self.summaries.append(messages)
        return AIMessage(content="Team needs API and ten users, budget INR10000/month.")


def settings(**overrides):
    return SimpleNamespace(
        memory_token_limit=overrides.get("memory_token_limit", 6000),
        memory_keep_messages=overrides.get("memory_keep_messages", 6),
        agent_recursion_limit=overrides.get("agent_recursion_limit", 16),
    )


def available_tools(calls):
    @tool
    async def company_rag(query: str) -> dict:
        """Search company documents."""
        calls.append(("rag", query))
        return {
            "sources": [{"url": "https://attoforce.ai/", "title": "Company", "text": "Evidence"}]
        }

    @tool
    async def neo4j_query(query: str) -> dict:
        """Read products from Neo4j."""
        calls.append(("neo4j", query))
        return {"products": [{"id": "salesflow", "name": "SalesFlow"}]}

    return [company_rag, neo4j_query]


def tool_chunk(name, arguments, call_id):
    return AIMessageChunk(
        content="",
        tool_call_chunks=[
            {
                "name": name,
                "args": json.dumps(arguments),
                "id": call_id,
                "index": 0,
            }
        ],
    )


@pytest.mark.asyncio
async def test_model_chooses_multiple_tools_after_inspecting_results():
    calls = []
    model = ScriptedModel(
        [
            [tool_chunk("neo4j_query", {"query": "inspect CRM"}, "first")],
            [tool_chunk("company_rag", {"query": "company support policy"}, "second")],
            [AIMessageChunk(content="Recommended "), AIMessageChunk(content="SalesFlow.")],
        ]
    )
    assistant = Assistant(settings(), model, available_tools(calls))
    events = [event async for event in assistant.stream("CRM and support policy")]
    assert model.bound == ["company_rag", "neo4j_query"]
    assert calls == [("neo4j", "inspect CRM"), ("rag", "company support policy")]
    assert any(isinstance(item, ToolMessage) for item in model.inputs[1])
    assert any(
        isinstance(item, ToolMessage) and item.tool_call_id == "second" for item in model.inputs[2]
    )
    assert [event["text"] for event in events if event["type"] == "token"] == [
        "Recommended ",
        "SalesFlow.",
    ]
    assert events[-1]["type"] == "done"
    assert events[-1]["answer"] == "Recommended SalesFlow."
    assert events[-1]["sources"][0]["title"] == "Company"


@pytest.mark.asyncio
async def test_greeting_has_no_unconditional_catalog_or_rag_calls():
    calls = []
    model = ScriptedModel([[AIMessageChunk(content="Hello!")]])
    result = await Assistant(settings(), model, available_tools(calls)).chat("Hello")
    assert result["answer"] == "Hello!"
    assert calls == []


@pytest.mark.asyncio
async def test_thread_memory_is_reused_and_isolated_without_history_replay():
    model = ScriptedModel(
        [
            [AIMessageChunk(content="I remember your ten-person team.")],
            [AIMessageChunk(content="The same ten people.")],
            [AIMessageChunk(content="New conversation.")],
        ]
    )
    assistant = Assistant(settings(), model, available_tools([]))
    first = await assistant.chat("We have ten people")
    await assistant.chat("How many people?", first["thread_id"])
    await assistant.chat("Hello")
    assert [item.content for item in model.inputs[1] if isinstance(item, HumanMessage)] == [
        "We have ten people",
        "How many people?",
    ]
    assert "We have ten people" not in str(model.inputs[2])


@pytest.mark.asyncio
async def test_token_is_delivered_before_generation_finishes():
    release = asyncio.Event()

    class SlowModel(ScriptedModel):
        async def astream(self, messages):
            yield AIMessageChunk(content="First")
            await release.wait()
            yield AIMessageChunk(content=" second")

    assistant = Assistant(settings(), SlowModel([]), available_tools([]))
    stream = assistant.stream("Hi")
    assert (await anext(stream))["type"] == "session"
    event = await asyncio.wait_for(anext(stream), timeout=1)
    assert event == {"type": "token", "text": "First"}
    release.set()
    remaining = [event async for event in stream]
    assert remaining[-1]["answer"] == "First second"


@pytest.mark.asyncio
async def test_empty_generation_is_rejected_instead_of_publishing_blank_answer():
    model = ScriptedModel([[AIMessageChunk(content="")]])
    assistant = Assistant(settings(), model, available_tools([]))
    with pytest.raises(ValueError, match="no response|empty"):
        await assistant.chat("Hi")


@pytest.mark.asyncio
async def test_unconfigured_model_does_not_break_admin_app_construction():
    assistant = Assistant(settings(), None, available_tools([]))
    with pytest.raises(ValueError, match="Configure Gemini"):
        await assistant.chat("Hi")
