"""Named Vertex vector writes and coverage checks; never alter the legacy vector."""

import math

from weaviate.classes.config import Configure

from company_compass.utils.documents import chunk_id


def ensure_named_vector(collection, name: str) -> None:
    configuration = collection.config.get()
    if name not in configuration.vector_config:
        collection.config.add_vector(
            vector_config=Configure.Vectors.self_provided(
                name=name, vector_index_config=Configure.VectorIndex.hfresh()
            )
        )


def valid_vector(vector, dimensions: int) -> bool:
    return (
        isinstance(vector, list)
        and len(vector) == dimensions
        and all(isinstance(value, (int, float)) and math.isfinite(value) for value in vector)
    )


def stored_vector(collection, identity, name: str):
    point = collection.query.fetch_object_by_id(identity, include_vector=True)
    return point.vector.get(name) if point is not None else None


def write_vectors(
    collection, chunks: list[dict], vectors: list[list[float]], name: str, dimensions: int
) -> None:
    if len(chunks) != len(vectors) or not all(valid_vector(v, dimensions) for v in vectors):
        raise ValueError("Embedding output does not match the required chunk count/dimensions")
    for chunk, vector in zip(chunks, vectors, strict=True):
        identity = chunk_id(chunk)
        if collection.data.exists(identity):
            collection.data.update(uuid=identity, vector={name: vector})
        else:
            collection.data.insert(properties=chunk, uuid=identity, vector={name: vector})


def verify_vectors(collection, chunks: list[dict], name: str, dimensions: int) -> int:
    for chunk in chunks:
        if not valid_vector(stored_vector(collection, chunk_id(chunk), name), dimensions):
            raise ValueError("A published document chunk has no valid target vector")
    return len(chunks)
