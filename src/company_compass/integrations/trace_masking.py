"""Redact trace content at SDK creation and final OpenTelemetry export."""

import json
import re

_PRIVATE_KEY = re.compile(
    r"-----BEGIN [^-]*PRIVATE KEY-----.*?-----END [^-]*PRIVATE KEY-----", re.S
)
_EMAIL = re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}")
_TOKEN = re.compile(r"\b(?:sk-lf-|pk-lf-|sk-)[A-Za-z0-9_-]+")
_SENSITIVE_KEY = re.compile(
    r"password|secret|api[_-]?key|authorization|credential|signature|private[_-]?key|"
    r"(?:api|auth|access|refresh)[_-]?token",
    re.I,
)


class TraceMask:
    def __init__(self, settings):
        self.capture = settings.langfuse_capture_content
        self.secrets = [
            value.get_secret_value()
            for _, value in settings
            if hasattr(value, "get_secret_value") and len(value.get_secret_value()) >= 6
        ]

    def redact(self, data):
        if isinstance(data, str):
            for secret in self.secrets:
                data = data.replace(secret, "[redacted]")
            data = _PRIVATE_KEY.sub("[redacted private key]", data)
            return _EMAIL.sub("[redacted email]", _TOKEN.sub("[redacted token]", data))
        if isinstance(data, dict):
            if data.get("thought") or data.get("type") in {"thinking", "reasoning"}:
                return "[internal reasoning omitted]"
            return {
                key: "[redacted]" if _SENSITIVE_KEY.search(str(key)) else self.redact(value)
                for key, value in data.items()
                if key not in {"thought", "reasoning_content"}
            }
        if isinstance(data, (list, tuple)):
            return [self.redact(value) for value in data]
        return data

    def content(self, data):
        return self.redact(data) if self.capture else "[content capture disabled]"

    def export(self, *, params):
        from langfuse.types import MaskOtelSpansResult, OtelSpanPatch

        patches = {}
        for identifier, span in params.spans.items():
            updates = {}
            for key, value in span.attributes.items():
                if _SENSITIVE_KEY.search(key):
                    updates[key] = "[redacted]"
                    continue
                if key.startswith("langfuse.observation.") and any(
                    part in key for part in ("usage_details", "cost_details")
                ):
                    continue  # Provider counts remain intact, never estimated or overwritten.
                is_content = any(
                    part in key
                    for part in (
                        "input",
                        "output",
                        "prompt",
                        "completion",
                        "status_message",
                        "exception.message",
                        "exception.stacktrace",
                    )
                )
                if is_content and not self.capture:
                    updates[key] = "[content capture disabled]"
                elif isinstance(value, str):
                    try:
                        decoded = json.loads(value)
                    except (ValueError, TypeError):
                        updates[key] = self.redact(value)
                    else:
                        updates[key] = json.dumps(self.redact(decoded), ensure_ascii=False)
                elif isinstance(value, (list, tuple)):
                    updates[key] = self.redact(value)
            patches[identifier] = OtelSpanPatch(set_attributes=updates)
        return MaskOtelSpansResult(span_patches=patches)
