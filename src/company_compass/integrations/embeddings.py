"""Vertex retrieval embeddings with explicit dimensions and normalized output."""

import math

from company_compass.core.settings import Settings

from .google_client import create_google_client


class VertexEmbeddingClient:
    """One synchronous SDK client per batch; no connection at construction time."""

    def __init__(self, settings: Settings):
        self.settings = settings

    def embed_documents(self, chunks: list[dict]) -> list[list[float]]:
        if not chunks:
            return []
        # Validate the complete input before making any billable request.
        for chunk in chunks:
            self._validate_text(chunk.get("text"))
            if not isinstance(chunk.get("title", ""), str):
                raise ValueError("Embedding document title must be text")
        return self._embed(chunks, task_type="RETRIEVAL_DOCUMENT")

    def embed_query(self, query: str) -> list[float]:
        self._validate_text(query)
        return self._embed([{"text": query}], task_type="RETRIEVAL_QUERY")[0]

    def _embed(self, chunks: list[dict], *, task_type: str) -> list[list[float]]:
        from google.genai import types

        if not self.settings.embedding_model:
            raise ValueError("Configure an embedding model before generating vectors")
        client = create_google_client(
            self.settings, vertexai=True, location=self.settings.google_embedding_location
        )
        try:
            vectors = []
            for chunk in chunks:
                # Vertex gemini-embedding-001 supports one input text per request.
                config = types.EmbedContentConfig(
                    task_type=task_type,
                    output_dimensionality=self.settings.embedding_dimensions,
                    title=(chunk.get("title") or None)
                    if task_type == "RETRIEVAL_DOCUMENT"
                    else None,
                )
                response = client.models.embed_content(
                    model=self.settings.embedding_model, contents=chunk["text"], config=config
                )
                embeddings = getattr(response, "embeddings", None)
                if not embeddings or len(embeddings) != 1:
                    raise ValueError("The provider must return exactly one embedding per input")
                vectors.append(self._normalize(getattr(embeddings[0], "values", None)))
            return vectors
        finally:
            client.close()

    def _normalize(self, values) -> list[float]:
        if (
            not isinstance(values, (list, tuple))
            or len(values) != self.settings.embedding_dimensions
        ):
            raise ValueError("The embedding vector has an unexpected dimension")
        if any(type(value) not in (int, float) or not math.isfinite(value) for value in values):
            raise ValueError("The embedding vector must contain finite numeric values")
        norm = math.hypot(*values)
        if not norm or not math.isfinite(norm):
            raise ValueError("The embedding vector must have a finite nonzero norm")
        # Reduced gemini-embedding-001 vectors are not automatically normalized.
        return [float(value / norm) for value in values]

    @staticmethod
    def _validate_text(text):
        if not isinstance(text, str) or not text.strip():
            raise ValueError("Embedding input text cannot be empty")
