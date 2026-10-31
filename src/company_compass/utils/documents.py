"""Pure document identity, legacy compatibility, and chunk construction helpers."""

import hashlib
import json
from datetime import UTC, datetime
from uuid import NAMESPACE_URL, uuid5

DATASET = "attoforce-company-v1"
MAX_BYTES = 2_000_000


def validate_edit(title: str, content: str, revision: int) -> tuple[str, str]:
    if not isinstance(title, str) or not 1 <= len(title.strip()) <= 250:
        raise ValueError("Document title must contain between 1 and 250 characters")
    if not isinstance(content, str) or not content.strip():
        raise ValueError("Document content cannot be empty")
    if len(content.encode("utf-8")) > MAX_BYTES:
        raise ValueError("Document content exceeds the two-megabyte limit")
    if isinstance(revision, bool) or not isinstance(revision, int) or revision < 1:
        raise ValueError("Expected revision must be a positive integer")
    return title.strip(), content


def document_version(title: str, content: str) -> str:
    encoded = json.dumps(
        {"title": title, "content": content},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def legacy_content(chunks: list[dict]) -> str:
    """Remove the old chunker's maximum 50-word overlap where it matches exactly."""
    words: list[str] = []
    for chunk in sorted(chunks, key=lambda item: item.get("chunk_index", 0)):
        current = chunk.get("text", "").split()
        overlap = 0
        for size in range(min(50, len(words), len(current)), 0, -1):
            if words[-size:] == current[:size]:
                overlap = size
                break
        words.extend(current[overlap:])
    return " ".join(words)


def hydrate_document(url: str, record: dict) -> dict:
    chunks = record.get("chunks", [])
    first = chunks[0] if chunks else {}
    return {
        **record,
        "id": record.get("id") or str(uuid5(NAMESPACE_URL, DATASET + ":" + url)),
        "title": record.get("title", first.get("title", url)),
        "content": record["content"] if "content" in record else legacy_content(chunks),
        "source_url": record.get("source_url", url if url.startswith("https://") else None),
        "revision": record.get("revision", 1),
        "observed_at": record.get("observed_at", first.get("observed_at", "")),
        "source_kind": record.get("source_kind", "official_web"),
    }


def make_document(
    url: str, title: str, content: str, source_kind: str, previous: dict | None
) -> dict:
    version = document_version(title, content)
    observed = datetime.now(UTC).isoformat()
    words = content.split()
    chunks = [
        {
            "text": " ".join(words[start : start + 300]),
            "title": title,
            "url": url,
            "document_version": version,
            "observed_at": observed,
            "dataset_id": DATASET,
            "chunk_index": index,
        }
        for index, start in enumerate(range(0, len(words), 250))
    ]
    return {
        "id": previous["id"] if previous else str(uuid5(NAMESPACE_URL, DATASET + ":" + url)),
        "title": title,
        "content": content,
        "source_url": url if url.startswith("https://") else None,
        "revision": previous["revision"] + 1 if previous else 1,
        "source_kind": source_kind,
        "observed_at": observed,
        "version": version,
        "chunks": chunks,
    }


def document_result(document: dict, include_content: bool = False) -> dict:
    fields = ("id", "title", "source_url", "revision", "version", "observed_at", "source_kind")
    result = {key: document[key] for key in fields}
    result["chunk_count"] = len(document["chunks"])
    if include_content:
        result["content"] = document["content"]
    return result


def chunk_id(chunk: dict):
    return uuid5(
        NAMESPACE_URL, f"{chunk['url']}:{chunk['document_version']}:{chunk['chunk_index']}"
    )
