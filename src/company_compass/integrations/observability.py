"""One request observation with native LangChain generations/tools beneath it."""

import asyncio
import logging
from dataclasses import dataclass, field
from uuid import uuid4

from company_compass.integrations.trace_masking import TraceMask

logger = logging.getLogger(__name__)


@dataclass
class TraceTurn:
    config: dict = field(default_factory=dict)
    trace_id: str | None = None
    observation: object | None = None

    def finish(self, *, answer=None, status="completed", error_type=None):
        if self.observation is None:
            return
        try:
            self.observation.update(
                output=answer,
                level="ERROR"
                if status == "error"
                else "WARNING"
                if status == "cancelled"
                else "DEFAULT",
                status_message=error_type if status == "error" else status,
            ).end()
        except Exception:
            logger.warning("Langfuse could not complete an observation")
        finally:
            self.observation = None


class Observability:
    def __init__(self, settings, *, client_factory=None, handler_factory=None):
        self.client = None
        self.public_key = settings.langfuse_public_key.get_secret_value()
        self.masker = TraceMask(settings)
        self.mask = self.masker.content
        if not (
            settings.langfuse_enabled
            and self.public_key
            and settings.langfuse_secret_key.get_secret_value()
        ):
            return
        try:
            if client_factory is None or handler_factory is None:
                from langfuse import Langfuse
                from langfuse.langchain import CallbackHandler

                client_factory = client_factory or Langfuse
                handler_factory = handler_factory or CallbackHandler
            self.client = client_factory(
                public_key=self.public_key,
                secret_key=settings.langfuse_secret_key.get_secret_value(),
                base_url=settings.langfuse_base_url,
                environment=settings.langfuse_environment,
                mask=self.mask,
                mask_otel_spans=self.masker.export,
                timeout=5,
                flush_interval=2,
            )
            self.handler_factory = handler_factory
        except Exception:
            logger.warning("Langfuse initialization failed; chat remains available")

    def start_turn(self, thread_id: str, message: str) -> TraceTurn:
        if self.client is None:
            return TraceTurn()
        observation = None
        try:
            from langfuse import propagate_attributes

            trace_id = uuid4().hex
            # A short synchronous scope sets request attributes without retaining
            # context-manager tokens across async-generator yields/disconnects.
            with propagate_attributes(
                session_id=thread_id,
                trace_name="company-compass-chat",
                tags=["company-compass", "chat"],
            ):
                observation = self.client.start_observation(
                    as_type="span",
                    name="company-compass-chat",
                    trace_context={"trace_id": trace_id},
                    input={"message": message},
                )
            handler = self.handler_factory(
                public_key=self.public_key,
                trace_context={"trace_id": trace_id, "parent_span_id": observation.id},
            )
            return TraceTurn(
                trace_id=trace_id,
                observation=observation,
                config={
                    "callbacks": [handler],
                    "run_name": "company-compass-workflow",
                    "tags": ["company-compass", "chat"],
                    "metadata": {
                        "langfuse_session_id": thread_id,
                        "langfuse_trace_name": "company-compass-chat",
                        "langfuse_tags": ["company-compass", "chat"],
                    },
                },
            )
        except Exception:
            if observation is not None:
                try:
                    observation.end()
                except Exception:
                    pass
            logger.warning("Langfuse turn setup failed; chat remains available")
            return TraceTurn()

    async def aclose(self):
        if self.client is not None:
            try:
                await asyncio.to_thread(self.client.shutdown)
            except Exception:
                logger.warning("Langfuse shutdown could not finish exporting traces")
