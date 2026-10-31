"""Real SDK/framework export with fake inference; no cloud traffic or paid calls."""

from uuid import uuid4

import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessageChunk
from langchain_core.outputs import ChatGenerationChunk
from langfuse import Langfuse
from langfuse.langchain import CallbackHandler
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from company_compass.agents.assistant import Assistant
from company_compass.core.settings import Settings
from company_compass.integrations.observability import Observability


class UsageModel(BaseChatModel):
    report_usage: bool = True

    @property
    def _llm_type(self):
        return "fake-gemini"

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        raise NotImplementedError

    async def _astream(self, messages, stop=None, run_manager=None, **kwargs):
        yield ChatGenerationChunk(
            message=AIMessageChunk(
                content="Supported answer.",
                response_metadata={"model_name": "gemini-test"},
                usage_metadata={
                    "input_tokens": 20,
                    "output_tokens": 10,
                    "total_tokens": 30,
                    "input_token_details": {"cache_read": 4},
                    "output_token_details": {"reasoning": 3},
                }
                if self.report_usage
                else None,
            )
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("report_usage,capture", [(True, True), (False, True), (True, False)])
async def test_native_callback_exports_one_generation_with_usage_and_request_hierarchy(
    report_usage, capture
):
    import json

    exporter = InMemorySpanExporter()
    options = Settings(
        _env_file=None,
        langfuse_public_key="test-" + uuid4().hex,
        langfuse_secret_key="test-secret",
        langfuse_capture_content=capture,
    )
    telemetry = Observability(
        options,
        client_factory=lambda **kwargs: Langfuse(
            **kwargs,
            tracer_provider=TracerProvider(),
            span_exporter=exporter,
        ),
        handler_factory=CallbackHandler,
    )
    assistant = Assistant(options, UsageModel(report_usage=report_usage), [], telemetry)
    result = await assistant.chat("Give an answer")
    await telemetry.aclose()
    spans = exporter.get_finished_spans()
    assert len({span.context.trace_id for span in spans}) == 1
    assert result["trace_id"] == f"{spans[0].context.trace_id:032x}"
    span_ids = {span.context.span_id for span in spans}
    roots = [span for span in spans if span.parent is None or span.parent.span_id not in span_ids]
    assert len(roots) == 1 and roots[0].name == "company-compass-chat"
    generations = [
        s for s in spans if s.attributes.get("langfuse.observation.type") == "generation"
    ]
    assert len(generations) == 1
    usage = json.loads(generations[0].attributes.get("langfuse.observation.usage_details", "{}"))
    if report_usage:
        assert usage == {
            "input": 16,
            "input_cache_read": 4,
            "output": 7,
            "output_reasoning": 3,
            "total": 30,
        }
    else:
        assert not usage  # Missing provider usage is unknown, never fabricated as zero.
    assert all(s.attributes.get("session.id") == result["thread_id"] for s in spans)
    if not capture:
        assert "Give an answer" not in str([s.attributes for s in spans])
        assert "Supported answer" not in str([s.attributes for s in spans])


@pytest.mark.asyncio
async def test_error_and_cancellation_end_request_observation_without_raw_error_text():
    import asyncio
    from unittest.mock import Mock

    for failure in (RuntimeError("private detail"),):

        class FailingModel(UsageModel):
            async def _astream(self, *args, failure=failure, **kwargs):
                raise failure
                yield

        root = Mock()
        client = Mock()
        client.start_observation.return_value = root
        telemetry = Observability(
            Settings(_env_file=None, langfuse_public_key="public", langfuse_secret_key="secret"),
            client_factory=lambda client=client, **kwargs: client,
            handler_factory=lambda **kwargs: Mock(),
        )
        # This case only checks service ownership. Native callback export is tested above.
        turn = telemetry.start_turn("thread", "question")
        turn.config = {}
        telemetry.start_turn = lambda *args, turn=turn: turn
        assistant = Assistant(Settings(_env_file=None), FailingModel(), [], telemetry)
        with pytest.raises(type(failure)):
            await assistant.chat("Question")
        update = root.update.call_args.kwargs
        assert update["level"] == (
            "WARNING" if isinstance(failure, asyncio.CancelledError) else "ERROR"
        )
        assert "private detail" not in str(update)
        root.update.return_value.end.assert_called_once()


@pytest.mark.asyncio
async def test_closing_stream_ends_request_as_cancelled():
    from unittest.mock import Mock

    root = Mock()
    telemetry = Mock()
    from company_compass.integrations.observability import TraceTurn

    telemetry.start_turn.return_value = TraceTurn(observation=root)
    assistant = Assistant(Settings(_env_file=None), UsageModel(), [], telemetry)
    stream = assistant.stream("Question")
    await anext(stream)
    await anext(stream)
    await stream.aclose()
    assert root.update.call_args.kwargs["level"] == "WARNING"
    root.update.return_value.end.assert_called_once()


@pytest.mark.asyncio
async def test_cancelled_native_stream_closes_generation_and_request_without_fake_usage():
    import asyncio
    import json

    class PausedModel(UsageModel):
        async def _astream(self, messages, stop=None, run_manager=None, **kwargs):
            yield ChatGenerationChunk(message=AIMessageChunk(content="Partial answer"))
            await asyncio.Event().wait()

    exporter = InMemorySpanExporter()
    options = Settings(
        _env_file=None,
        langfuse_public_key="test-" + uuid4().hex,
        langfuse_secret_key="test-secret",
    )
    telemetry = Observability(
        options,
        client_factory=lambda **kwargs: Langfuse(
            **kwargs,
            tracer_provider=TracerProvider(),
            span_exporter=exporter,
        ),
        handler_factory=CallbackHandler,
    )
    stream = Assistant(options, PausedModel(), [], telemetry).stream("Question")
    await anext(stream)
    assert (await anext(stream))["type"] == "token"
    await stream.aclose()
    await telemetry.aclose()
    spans = exporter.get_finished_spans()
    generations = [
        s for s in spans if s.attributes.get("langfuse.observation.type") == "generation"
    ]
    assert len(generations) == 1 and generations[0].end_time is not None
    assert not json.loads(generations[0].attributes.get("langfuse.observation.usage_details", "{}"))
    request = next(s for s in spans if s.name == "company-compass-chat")
    assert request.attributes["langfuse.observation.level"] == "WARNING"
