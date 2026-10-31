from types import SimpleNamespace
from unittest.mock import Mock

from company_compass.integrations.observability import Observability


def settings(**values):
    from company_compass.core.settings import Settings

    return Settings(_env_file=None, **values)


def test_unconfigured_observability_is_disabled_without_initializing_sdk():
    factory = Mock()
    telemetry = Observability(settings(), client_factory=factory)
    assert telemetry.start_turn("thread", "private question").config == {}
    factory.assert_not_called()


def test_each_turn_gets_one_new_handler_and_session_correlation():
    client = Mock()
    handler_factory = Mock(side_effect=lambda **kwargs: SimpleNamespace(**kwargs))
    telemetry = Observability(
        settings(langfuse_public_key="public", langfuse_secret_key="secret"),
        client_factory=Mock(return_value=client),
        handler_factory=handler_factory,
    )
    first = telemetry.start_turn("same-thread", "question")
    second = telemetry.start_turn("same-thread", "next question")
    assert len(first.config["callbacks"]) == 1
    assert first.config["callbacks"][0] is not second.config["callbacks"][0]
    assert first.config["metadata"]["langfuse_session_id"] == "same-thread"
    assert first.trace_id != second.trace_id


def test_mask_hides_content_by_default_and_redacts_secrets_when_enabled():
    factory = Mock(return_value=Mock())
    telemetry = Observability(
        settings(langfuse_public_key="public", langfuse_secret_key="private-langfuse-key"),
        client_factory=factory,
        handler_factory=Mock(),
    )
    assert telemetry.mask({"question": "private data"}) == "[content capture disabled]"
    telemetry = Observability(
        settings(
            langfuse_public_key="public",
            langfuse_secret_key="private-langfuse-key",
            langfuse_capture_content=True,
            neo4j_password="private-db-password",
        ),
        client_factory=factory,
        handler_factory=Mock(),
    )
    masked = telemetry.mask({"input": "private-langfuse-key private-db-password user@example.com"})
    assert "private-" not in str(masked)
    assert "user@example.com" not in str(masked)


def test_telemetry_failure_does_not_prevent_chat_or_expose_exception():
    telemetry = Observability(
        settings(langfuse_public_key="public", langfuse_secret_key="secret"),
        client_factory=Mock(side_effect=RuntimeError("private credentials")),
    )
    assert telemetry.start_turn("thread", "question").config == {}


def test_callback_setup_and_cleanup_failures_do_not_prevent_chat():
    client = Mock()
    client.start_observation.return_value.end.side_effect = RuntimeError("cleanup failed")
    telemetry = Observability(
        settings(langfuse_public_key="public", langfuse_secret_key="secret"),
        client_factory=Mock(return_value=client),
        handler_factory=Mock(side_effect=RuntimeError("handler failed")),
    )
    assert telemetry.start_turn("thread", "question").config == {}


def test_export_redacts_token_attributes_and_reasoning_but_preserves_usage():
    telemetry = Observability(settings(langfuse_capture_content=True))
    from langfuse.types import MaskOtelSpansParams, OtelSpanData, OtelSpanIdentifier

    identifier = OtelSpanIdentifier(trace_id="a" * 32, span_id="b" * 16)
    source = {
        "api_token": "unknown-private-token",
        "access_token": "another-token",
        "langfuse.observation.usage_details": '{"input":20,"output":8,"output_reasoning":2}',
        "langfuse.observation.output": (
            '[{"type":"thinking","text":"hidden reasoning"},{"type":"text","text":"public"}]'
        ),
    }
    result = telemetry.masker.export(
        params=MaskOtelSpansParams(
            spans={
                identifier: OtelSpanData(
                    trace_id=identifier.trace_id,
                    span_id=identifier.span_id,
                    parent_span_id=None,
                    name="test",
                    instrumentation_scope_name="test",
                    instrumentation_scope_version=None,
                    attributes=source,
                    resource_attributes={},
                )
            }
        )
    )
    updated = {**source, **result.span_patches[identifier].set_attributes}
    assert "unknown-private-token" not in str(updated)
    assert "another-token" not in str(updated)
    assert "hidden reasoning" not in str(updated)
    assert (
        updated["langfuse.observation.usage_details"]
        == source["langfuse.observation.usage_details"]
    )
    assert "public" in updated["langfuse.observation.output"]


def test_thought_flag_and_private_key_fields_do_not_export_hidden_text():
    telemetry = Observability(settings(langfuse_capture_content=True))
    result = telemetry.mask(
        {
            "blocks": [{"thought": True, "text": "hidden"}, {"type": "text", "text": "visible"}],
            "private_key": "unrecognized-key-value",
        }
    )
    assert "hidden" not in str(result)
    assert "unrecognized-key-value" not in str(result)
    assert "visible" in str(result)


def test_metadata_only_export_masks_provider_error_content_without_losing_status_or_usage():
    from langfuse.types import MaskOtelSpansParams, OtelSpanData, OtelSpanIdentifier

    telemetry = Observability(settings(langfuse_capture_content=False))
    identifier = OtelSpanIdentifier(trace_id="c" * 32, span_id="d" * 16)
    source = {
        "langfuse.observation.status_message": "Provider rejected private customer ACCT99123",
        "exception.message": "Private customer ACCT99123 requested invalid data",
        "exception.stacktrace": "ProviderError: ACCT99123 at /private/customer/path",
        "exception.type": "ProviderError",
        "langfuse.observation.level": "ERROR",
        "langfuse.observation.usage_details": '{"input":20,"output":8}',
    }
    result = telemetry.masker.export(
        params=MaskOtelSpansParams(
            spans={
                identifier: OtelSpanData(
                    trace_id=identifier.trace_id,
                    span_id=identifier.span_id,
                    parent_span_id=None,
                    name="test",
                    instrumentation_scope_name="test",
                    instrumentation_scope_version=None,
                    attributes=source,
                    resource_attributes={},
                )
            }
        )
    )
    updated = {**source, **result.span_patches[identifier].set_attributes}
    assert "ACCT99123" not in str(updated)
    assert "/private/customer/path" not in str(updated)
    assert updated["exception.type"] == "ProviderError"
    assert updated["langfuse.observation.level"] == "ERROR"
    assert (
        updated["langfuse.observation.usage_details"]
        == source["langfuse.observation.usage_details"]
    )
