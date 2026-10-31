import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest

from company_compass.core.settings import Settings
from company_compass.services.knowledge import (
    DocumentConflict,
    DocumentIndexingError,
    KnowledgeService,
    validate_source_url,
)


@pytest.mark.parametrize(
    "url",
    [
        "http://attoforce.ai/",
        "https://example.com/",
        "https://attoforce.ai@127.0.0.1/",
        "file:///etc/passwd",
    ],
)
def test_ingestion_rejects_non_official_sources(url):
    with pytest.raises(ValueError):
        validate_source_url(url, "attoforce.ai")


def test_official_https_source_is_accepted():
    assert validate_source_url("https://attoforce.ai/about/", "attoforce.ai")


@pytest.mark.parametrize(
    "url",
    [
        "https://attoforce.ai:444/",
        "https://user@attoforce.ai/",
        "https://localhost/",
        "https://attoforce.ai.evil.test/",
    ],
)
def test_ingestion_rejects_unsafe_authority(url):
    with pytest.raises(ValueError):
        validate_source_url(url, "attoforce.ai")


def service(tmp_path, mode="local"):
    return KnowledgeService(
        Settings(_env_file=None, app_mode=mode, knowledge_path=tmp_path / "knowledge.json")
    )


def test_local_refresh_replaces_old_evidence_and_reports_lexical_mode(tmp_path, monkeypatch):
    knowledge = service(tmp_path)
    monkeypatch.setattr(knowledge, "_fetch", lambda url: ("Company", "Alpha original fact"))
    assert knowledge.ingest(["https://attoforce.ai/"])["ingested"] == 1
    monkeypatch.setattr(knowledge, "_fetch", lambda url: ("Company", "Beta updated fact"))
    knowledge.ingest(["https://attoforce.ai/"])
    assert not knowledge.search("Alpha")["sources"]
    result = knowledge.search("Beta")
    assert "Beta" in result["sources"][0]["text"]
    assert "lexical" in " ".join(result["warnings"]).lower()


def test_failed_indexing_preserves_published_version(tmp_path, monkeypatch):
    knowledge = service(tmp_path)
    monkeypatch.setattr(knowledge, "_fetch", lambda url: ("Company", "Original evidence"))
    knowledge.ingest(["https://attoforce.ai/"])
    monkeypatch.setattr(knowledge, "_fetch", lambda url: ("Company", "Replacement evidence"))

    def fail(*args):
        raise RuntimeError("provider-secret-must-not-leak")

    monkeypatch.setattr(knowledge, "_index_chunks", fail)
    result = knowledge.ingest(["https://attoforce.ai/"])
    assert result["ingested"] == 0
    assert "provider-secret" not in str(result)
    assert knowledge.search("Original")["sources"]


def test_cloud_search_rejects_partial_or_obsolete_versions(tmp_path, monkeypatch):
    knowledge = service(tmp_path, "cloud")
    monkeypatch.setattr(knowledge, "_fetch", lambda url: ("Company", "Published evidence"))
    monkeypatch.setattr(knowledge, "_index_chunks", lambda chunks: None)
    knowledge.ingest(["https://attoforce.ai/"])
    current = knowledge._documents()["https://attoforce.ai/"]["chunks"][0]
    stale = dict(current, document_version="unpublished", text="Stale evidence")
    monkeypatch.setattr(knowledge, "_query_cloud", lambda query: [stale, current])
    result = knowledge.search("evidence")
    assert len(result["sources"]) == 1
    assert result["sources"][0]["text"] == "Published evidence"


def test_cloud_retry_does_not_reinsert_already_staged_chunks(tmp_path, monkeypatch):
    knowledge = service(tmp_path, "cloud")
    known, batches = set(), []

    def insert_many(objects):
        batches.append(objects)
        known.update(str(obj.uuid) for obj in objects)
        return SimpleNamespace(has_errors=False)

    data = SimpleNamespace(exists=lambda uuid: str(uuid) in known, insert_many=insert_many)
    monkeypatch.setattr(knowledge, "_collection", lambda create=False: SimpleNamespace(data=data))
    chunks = [{"url": "https://attoforce.ai/", "document_version": "version", "chunk_index": 0}]
    knowledge._index_chunks(chunks)
    knowledge._index_chunks(chunks)
    assert len(batches) == 1


def test_fetch_evidence_never_publishes_or_indexes(tmp_path, monkeypatch):
    knowledge = service(tmp_path)
    monkeypatch.setattr(knowledge, "_fetch", lambda url: ("Official page", "Fetched evidence"))
    result = knowledge.fetch_evidence("https://attoforce.ai/about/")
    assert result["url"] == "https://attoforce.ai/about/"
    assert result["text"] == "Fetched evidence"
    assert result["observed_at"]
    assert not knowledge.path.exists()


def ingest_page(knowledge, monkeypatch, title="Company", text="Original evidence"):
    monkeypatch.setattr(knowledge, "_fetch", lambda url: (title, text))
    knowledge.ingest(["https://attoforce.ai/"])
    return knowledge.list_documents()[0]


def test_documents_preserve_identity_exact_content_and_increment_revision(tmp_path, monkeypatch):
    knowledge = service(tmp_path)
    original = ingest_page(knowledge, monkeypatch)
    content = "Updated heading\n\n  Exact whitespace and facts.\n"
    result = knowledge.replace_document(original["id"], " Edited title ", content, 1)
    assert result["id"] == original["id"]
    assert result["title"] == "Edited title"
    assert result["content"] == content
    assert result["revision"] == 2
    assert result["source_kind"] == "admin_edit"
    assert result["source_url"] == "https://attoforce.ai/"
    assert "content" not in knowledge.list_documents()[0]
    assert knowledge.get_document(original["id"])["content"] == content


def test_legacy_documents_are_discoverable_and_remove_chunk_overlap(tmp_path):
    import json

    knowledge = service(tmp_path)
    words = [f"word{index}" for index in range(400)]
    chunks = [
        {
            "title": "Legacy page",
            "text": " ".join(words[:300]),
            "url": "https://attoforce.ai/",
            "document_version": "legacy",
            "chunk_index": 0,
            "observed_at": "2026-10-31T00:00:00Z",
        },
        {
            "title": "Legacy page",
            "text": " ".join(words[250:]),
            "url": "https://attoforce.ai/",
            "document_version": "legacy",
            "chunk_index": 1,
            "observed_at": "2026-10-31T00:00:00Z",
        },
    ]
    knowledge.path.write_text(
        json.dumps({"local": {"https://attoforce.ai/": {"version": "legacy", "chunks": chunks}}}),
        encoding="utf-8",
    )
    metadata = knowledge.list_documents()[0]
    document = knowledge.get_document(metadata["id"])
    assert metadata["revision"] == 1
    assert metadata["source_kind"] == "official_web"
    assert document["content"] == " ".join(words)
    assert knowledge.list_documents()[0]["id"] == metadata["id"]


def test_stale_edit_is_rejected_without_reindexing(tmp_path, monkeypatch):
    knowledge = service(tmp_path)
    original = ingest_page(knowledge, monkeypatch)
    knowledge.replace_document(original["id"], "New", "Current content", 1)
    monkeypatch.setattr(knowledge, "_index_chunks", lambda chunks: pytest.fail("Must not index"))
    with pytest.raises(DocumentConflict):
        knowledge.replace_document(original["id"], "Old", "Stale content", 1)
    assert knowledge.get_document(original["id"])["content"] == "Current content"


def test_failed_admin_index_keeps_old_content_revision_and_sources(tmp_path, monkeypatch):
    knowledge = service(tmp_path)
    original = ingest_page(knowledge, monkeypatch)

    def fail(chunks):
        raise RuntimeError("provider-secret")

    monkeypatch.setattr(knowledge, "_index_chunks", fail)
    with pytest.raises(DocumentIndexingError, match="previous published") as error:
        knowledge.replace_document(original["id"], "New", "New content", 1)
    assert "provider-secret" not in str(error.value)
    assert knowledge.get_document(original["id"])["revision"] == 1
    assert knowledge.get_document(original["id"])["content"] == "Original evidence"
    result = knowledge.search("Original")["sources"][0]
    assert result["document_id"] == original["id"]
    assert result["document_revision"] == 1


def test_replacement_excludes_old_chunks_and_is_idempotent(tmp_path, monkeypatch):
    knowledge = service(tmp_path, "cloud")
    monkeypatch.setattr(knowledge, "_index_chunks", lambda chunks: None)
    monkeypatch.setattr(knowledge, "_cleanup_chunks", lambda old, new: None)
    original = ingest_page(knowledge, monkeypatch)
    old = knowledge._documents()["https://attoforce.ai/"]["chunks"][0]
    changed = knowledge.replace_document(original["id"], "New", "Replacement evidence", 1)
    current = knowledge._documents()["https://attoforce.ai/"]["chunks"][0]
    monkeypatch.setattr(knowledge, "_query_cloud", lambda query: [old, current])
    sources = knowledge.search("evidence")["sources"]
    assert len(sources) == 1
    assert sources[0]["text"] == "Replacement evidence"
    assert sources[0]["source_kind"] == "admin_edit"
    monkeypatch.setattr(knowledge, "_index_chunks", lambda chunks: pytest.fail("No reembedding"))
    repeated = knowledge.replace_document(original["id"], "New", "Replacement evidence", 2)
    assert repeated["revision"] == changed["revision"]


def test_url_refresh_cannot_overwrite_admin_edits(tmp_path, monkeypatch):
    knowledge = service(tmp_path)
    original = ingest_page(knowledge, monkeypatch)
    knowledge.replace_document(original["id"], "Edited", "Human reviewed text", 1)
    monkeypatch.setattr(knowledge, "_fetch", lambda url: pytest.fail("Do not fetch edited page"))
    result = knowledge.ingest(["https://attoforce.ai/"])
    assert result["ingested"] == 0
    assert "admin" in " ".join(result["warnings"]).lower()
    assert knowledge.get_document(original["id"])["content"] == "Human reviewed text"


def test_cleanup_failure_keeps_new_published_content(tmp_path, monkeypatch):
    knowledge = service(tmp_path)
    original = ingest_page(knowledge, monkeypatch)

    def fail(old, new):
        raise RuntimeError("cleanup failed")

    monkeypatch.setattr(knowledge, "_cleanup_chunks", fail)
    result = knowledge.replace_document(original["id"], "Updated", "New active content", 1)
    assert result["revision"] == 2
    assert result["warnings"]
    assert knowledge.get_document(original["id"])["content"] == "New active content"


def test_search_rechecks_publication_after_cloud_query(tmp_path, monkeypatch):
    knowledge = service(tmp_path, "cloud")
    monkeypatch.setattr(knowledge, "_index_chunks", lambda chunks: None)
    monkeypatch.setattr(knowledge, "_cleanup_chunks", lambda old, new: None)
    original = ingest_page(knowledge, monkeypatch)
    old = knowledge._documents()["https://attoforce.ai/"]["chunks"][0]

    def query_during_edit(query):
        knowledge.replace_document(original["id"], "Changed", "Updated content", 1)
        return [old]

    monkeypatch.setattr(knowledge, "_query_cloud", query_during_edit)
    assert knowledge.search("Original")["sources"] == []


@pytest.mark.parametrize(
    "title,content,revision", [("", "text", 1), ("T", " ", 1), ("T", "text", 0)]
)
def test_invalid_admin_document_is_not_published(tmp_path, monkeypatch, title, content, revision):
    knowledge = service(tmp_path)
    original = ingest_page(knowledge, monkeypatch)
    with pytest.raises(ValueError):
        knowledge.replace_document(original["id"], title, content, revision)
    assert knowledge.get_document(original["id"])["revision"] == 1


def test_cli_refresh_waits_for_admin_edit_in_another_process(tmp_path, monkeypatch):
    knowledge = service(tmp_path)
    original = ingest_page(knowledge, monkeypatch)
    ready, release, finished = (tmp_path / name for name in ("ready", "release", "finished"))
    script = """
import sys, time
from pathlib import Path
from company_compass.core.settings import Settings
from company_compass.services.knowledge import KnowledgeService
manifest, identity, ready, release, finished = map(Path, sys.argv[1:])
service = KnowledgeService(Settings(_env_file=None, app_mode='local', knowledge_path=manifest))
def stage(chunks):
    ready.write_text('indexing')
    deadline = time.monotonic() + 20
    while not release.exists():
        if time.monotonic() > deadline:
            raise RuntimeError('test coordination timeout')
        time.sleep(0.01)
service._index_chunks = stage
service.replace_document(str(identity), 'Admin title', 'Human reviewed content', 1)
finished.write_text('published')
"""
    process = subprocess.Popen(
        [
            sys.executable,
            "-c",
            script,
            str(knowledge.path),
            original["id"],
            str(ready),
            str(release),
            str(finished),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        deadline = time.monotonic() + 20
        while not ready.exists():
            assert process.poll() is None, process.communicate()[1]
            assert time.monotonic() < deadline, "First process did not reach indexing"
            time.sleep(0.01)

        def refresh_source(url):
            deadline = time.monotonic() + 20
            while not finished.exists():
                if time.monotonic() > deadline:
                    raise RuntimeError("test coordination timeout")
                time.sleep(0.01)
            return "Web title", "Stale refresh must not replace the administrator's edit"

        monkeypatch.setattr(knowledge, "_fetch", refresh_source)
        with ThreadPoolExecutor(max_workers=1) as executor:
            refresh = executor.submit(knowledge.ingest, ["https://attoforce.ai/"])
            time.sleep(0.2)
            release.write_text("continue", encoding="utf-8")
            result = refresh.result(timeout=20)
        stdout, stderr = process.communicate(timeout=20)
        assert process.returncode == 0, stderr or stdout
        assert result["ingested"] == 0
        assert knowledge.get_document(original["id"])["content"] == "Human reviewed content"
    finally:
        release.touch(exist_ok=True)
        if process.poll() is None:
            process.kill()
            process.communicate()


class VectorCollection:
    def __init__(self):
        self.points = {}
        self.query_calls = []
        self.data = SimpleNamespace(exists=self.exists, update=self.update, insert=self.insert)
        self.query = SimpleNamespace(fetch_object_by_id=self.fetch, hybrid=self.hybrid)

    def exists(self, identity):
        return str(identity) in self.points

    def fetch(self, identity, include_vector=False):
        return self.points.get(str(identity))

    def update(self, uuid, vector):
        self.points[str(uuid)].vector.update(vector)

    def insert(self, properties, uuid, vector):
        self.points[str(uuid)] = SimpleNamespace(properties=properties, vector=vector)

    def hybrid(self, **kwargs):
        self.query_calls.append(kwargs)
        return SimpleNamespace(objects=[])


class Embeddings:
    def __init__(self):
        self.document_calls = []
        self.query_calls = []

    def embed_documents(self, chunks):
        self.document_calls.append(chunks)
        return [[0.25] * 1536 for chunk in chunks]

    def embed_query(self, query):
        self.query_calls.append(query)
        return [0.5] * 1536


def vertex_service(tmp_path):
    knowledge = service(tmp_path, "cloud")
    knowledge.settings = knowledge.settings.model_copy(
        update={
            "embedding_provider": "vertex",
            "embedding_model": "gemini-embedding-001",
            "embedding_dimensions": 1536,
            "weaviate_vector_name": "google_1536",
        }
    )
    return knowledge


def test_vertex_index_backfills_existing_uuid_without_replacing_default_vector(
    tmp_path, monkeypatch
):
    from company_compass.utils.documents import chunk_id

    knowledge, collection, embedder = vertex_service(tmp_path), VectorCollection(), Embeddings()
    chunk = {
        "url": "https://attoforce.ai/",
        "document_version": "v1",
        "chunk_index": 0,
        "text": "Company facts",
        "title": "Company",
    }
    identity = chunk_id(chunk)
    collection.points[str(identity)] = SimpleNamespace(vector={"default": [0.1] * 768})
    monkeypatch.setattr(knowledge, "_collection", lambda create=False: collection)
    monkeypatch.setattr(knowledge, "_embedder", lambda: embedder)
    knowledge._index_chunks([chunk])
    assert len(collection.points[str(identity)].vector["google_1536"]) == 1536
    assert collection.points[str(identity)].vector["default"] == [0.1] * 768
    assert embedder.document_calls == [[chunk]]


@pytest.mark.parametrize("provider,target", [("weaviate", "default"), ("vertex", "google_1536")])
def test_cloud_hybrid_targets_the_selected_named_vector(tmp_path, monkeypatch, provider, target):
    knowledge, collection, embedder = vertex_service(tmp_path), VectorCollection(), Embeddings()
    knowledge.settings = knowledge.settings.model_copy(update={"embedding_provider": provider})
    monkeypatch.setattr(knowledge, "_index_chunks", lambda chunks: None)
    ingest_page(knowledge, monkeypatch)
    monkeypatch.setattr(knowledge, "_collection", lambda create=False: collection)
    monkeypatch.setattr(knowledge, "_embedder", lambda: embedder)
    knowledge._query_cloud("Company facts")
    assert collection.query_calls[0]["target_vector"] == target
    if provider == "vertex":
        assert len(collection.query_calls[0]["vector"]) == 1536
        assert embedder.query_calls == ["Company facts"]
    else:
        assert "vector" not in collection.query_calls[0]


def test_migration_verifies_all_active_chunks_without_changing_document_revisions(
    tmp_path, monkeypatch
):
    from company_compass.utils.documents import chunk_id

    knowledge, collection, embedder = vertex_service(tmp_path), VectorCollection(), Embeddings()
    monkeypatch.setattr(knowledge, "_index_chunks", lambda chunks: None)
    ingest_page(knowledge, monkeypatch, text=" ".join(f"word{i}" for i in range(400)))
    manifest = knowledge.path.read_bytes()
    chunks = knowledge._documents()["https://attoforce.ai/"]["chunks"]
    collection.points[str(chunk_id(chunks[0]))] = SimpleNamespace(vector={"default": [0.1] * 768})
    monkeypatch.setattr(knowledge, "_collection", lambda create=False: collection)
    monkeypatch.setattr(knowledge, "_embedder", lambda: embedder)
    result = knowledge.migrate_embeddings()
    assert result["embedded_chunks"] == result["verified_chunks"] == len(chunks)
    assert result["dimensions"] == 1536
    assert all(len(point.vector["google_1536"]) == 1536 for point in collection.points.values())
    assert knowledge.path.read_bytes() == manifest


def test_migration_verification_failure_does_not_change_manifest_or_provider(tmp_path, monkeypatch):
    knowledge, collection, embedder = vertex_service(tmp_path), VectorCollection(), Embeddings()
    monkeypatch.setattr(knowledge, "_index_chunks", lambda chunks: None)
    ingest_page(knowledge, monkeypatch)
    manifest = knowledge.path.read_bytes()
    monkeypatch.setattr(knowledge, "_collection", lambda create=False: collection)
    monkeypatch.setattr(knowledge, "_embedder", lambda: embedder)
    monkeypatch.setattr(collection, "fetch", lambda *args, **kwargs: None)
    collection.query.fetch_object_by_id = collection.fetch
    with pytest.raises(DocumentIndexingError):
        knowledge.migrate_embeddings()
    assert knowledge.path.read_bytes() == manifest
    assert knowledge.settings.embedding_provider == "vertex"


def test_existing_collection_adds_only_the_new_self_provided_named_vector(tmp_path, monkeypatch):
    knowledge = vertex_service(tmp_path)
    added = []
    configured = {"default": SimpleNamespace(vectorizer="text2vec-weaviate")}

    def add_vector(*, vector_config):
        added.append(vector_config)
        configured[vector_config.name] = vector_config

    collection = SimpleNamespace(
        config=SimpleNamespace(
            get=lambda: SimpleNamespace(vector_config=configured), add_vector=add_vector
        )
    )
    collections = SimpleNamespace(exists=lambda name: True, get=lambda name: collection)
    monkeypatch.setattr(knowledge, "_connect", lambda: SimpleNamespace(collections=collections))
    assert knowledge._collection(create=True) is collection
    knowledge._collection(create=True)
    assert len(added) == 1
    assert added[0].name == "google_1536"
    assert added[0]._to_dict()["vectorIndexType"] == "hfresh"
    assert configured["default"].vectorizer == "text2vec-weaviate"


@pytest.mark.parametrize("provider", ["weaviate", "vertex"])
def test_new_assignment_collection_uses_free_tier_hfresh_index(tmp_path, monkeypatch, provider):
    knowledge = vertex_service(tmp_path)
    knowledge.settings = knowledge.settings.model_copy(update={"embedding_provider": provider})
    created, configured = [], {}

    def create(name, *, vector_config, properties):
        created.append(vector_config._to_dict())
        configured[vector_config.name or "default"] = vector_config

    collection = SimpleNamespace(
        config=SimpleNamespace(
            get=lambda: SimpleNamespace(vector_config=configured),
            add_vector=lambda **kwargs: pytest.fail("Creation already configured the named vector"),
        )
    )
    collections = SimpleNamespace(
        exists=lambda name: False, get=lambda name: collection, create=create
    )
    monkeypatch.setattr(knowledge, "_connect", lambda: SimpleNamespace(collections=collections))
    knowledge._collection(create=True)
    assert created[0]["vectorIndexType"] == "hfresh"
