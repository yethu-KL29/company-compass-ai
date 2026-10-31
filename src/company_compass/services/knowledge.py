"""Official-source ingestion, version publication, and company evidence retrieval."""

import json
import re
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from urllib.parse import urljoin, urlsplit, urlunsplit
from uuid import uuid4

import httpx
from bs4 import BeautifulSoup
from filelock import FileLock, Timeout

from company_compass.core.settings import Settings
from company_compass.integrations.knowledge_vectors import (
    ensure_named_vector,
    stored_vector,
    valid_vector,
    verify_vectors,
    write_vectors,
)
from company_compass.utils.documents import (
    DATASET,
    MAX_BYTES,
    chunk_id,
    document_result,
    hydrate_document,
    make_document,
    validate_edit,
)
from company_compass.utils.storage import atomic_write_json

_MANIFEST_LOCK = RLock()


class DocumentConflict(ValueError):
    """An administrator edited a document revision that has since changed."""


class DocumentIndexingError(RuntimeError):
    """New chunks failed to index; the prior publication remains authoritative."""


def validate_source_url(url: str, domain: str) -> str:
    """Only configured public company HTTPS URLs are eligible for ingestion."""
    parsed = urlsplit(url)
    allowed = {domain.lower(), "www." + domain.lower()}
    if (
        parsed.scheme != "https"
        or parsed.hostname not in allowed
        or parsed.username
        or parsed.password
        or parsed.port not in (None, 443)
        or parsed.hostname in {"localhost", "127.0.0.1", "::1"}
    ):
        raise ValueError("Only approved official-company HTTPS URLs are allowed")
    return urlunsplit(("https", parsed.netloc.lower(), parsed.path or "/", parsed.query, ""))


class KnowledgeService:
    """Single-host manifest publishes a page only after all new chunks are indexed."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.path = Path(settings.knowledge_path).resolve()
        self.client = None
        self.scope = (
            "local"
            if settings.app_mode == "local"
            else f"cloud:{settings.weaviate_url}:{settings.weaviate_collection}"
        )

    def _state(self) -> dict:
        if not self.path.exists():
            return {}
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _documents(self) -> dict:
        return self._state().get(self.scope, {})

    @contextmanager
    def _update_lock(self):
        """Serialize API and CLI writers that share this host's manifest file."""
        with _MANIFEST_LOCK:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            lock = FileLock(str(self.path) + ".lock")
            try:
                lock.acquire(timeout=60)
            except Timeout:
                raise DocumentConflict(
                    "Another document update is running; retry after it finishes"
                ) from None
            try:
                yield
            finally:
                lock.release()

    def list_documents(self) -> list[dict]:
        with _MANIFEST_LOCK:
            return [
                document_result(hydrate_document(url, record))
                for url, record in self._documents().items()
            ]

    def get_document(self, document_id: str) -> dict | None:
        with _MANIFEST_LOCK:
            for url, record in self._documents().items():
                document = hydrate_document(url, record)
                if document["id"] == document_id:
                    return document_result(document, include_content=True)
        return None

    def replace_document(
        self, document_id: str, title: str, content: str, expected_revision: int
    ) -> dict:
        title, content = validate_edit(title, content, expected_revision)
        with self._update_lock():
            for url, record in self._documents().items():
                previous = hydrate_document(url, record)
                if previous["id"] != document_id:
                    continue
                if previous["revision"] != expected_revision:
                    raise DocumentConflict(
                        "Document changed; reload it before publishing your edit"
                    )
                document, warnings, _ = self._write_document(
                    url, title, content, "admin_edit", previous
                )
                return {**document_result(document, include_content=True), "warnings": warnings}
        raise ValueError("Document not found")

    def add_document(self, title: str, content: str) -> dict:
        """Publish an administrator upload without inventing an official source URL."""
        title, content = validate_edit(title, content, 1)
        identity = f"urn:company-compass:upload:{uuid4()}"
        with self._update_lock():
            document, warnings, _ = self._write_document(
                identity, title, content, "admin_upload", None
            )
        return {**document_result(document, include_content=True), "warnings": warnings}

    def _publish(self, url: str, document: dict) -> None:
        with _MANIFEST_LOCK:
            state = self._state()
            state.setdefault(self.scope, {})[url] = document
            atomic_write_json(self.path, state)

    def _connect(self):
        if self.client is None:
            import weaviate
            from weaviate.classes.init import AdditionalConfig, Auth, Timeout

            if (
                not self.settings.weaviate_url
                or not self.settings.weaviate_api_key.get_secret_value()
            ):
                raise ValueError("Weaviate credentials are not configured")
            self.client = weaviate.connect_to_weaviate_cloud(
                cluster_url=self.settings.weaviate_url,
                auth_credentials=Auth.api_key(self.settings.weaviate_api_key.get_secret_value()),
                additional_config=AdditionalConfig(timeout=Timeout(init=10, query=20, insert=30)),
            )
        return self.client

    def _embedder(self):
        from company_compass.integrations.embeddings import VertexEmbeddingClient

        return VertexEmbeddingClient(self.settings)

    @property
    def _uses_vertex(self) -> bool:
        return getattr(self.settings, "embedding_provider", "weaviate") == "vertex"

    def _collection(self, create: bool = False):
        from weaviate.classes.config import Configure, DataType, Property

        client = self._connect()
        name = self.settings.weaviate_collection
        if not client.collections.exists(name):
            if not create:
                return None
            vector_config = (
                Configure.Vectors.self_provided(
                    name=self.settings.weaviate_vector_name,
                    vector_index_config=Configure.VectorIndex.hfresh(),
                )
                if self._uses_vertex
                else Configure.Vectors.text2vec_weaviate(
                    model="Snowflake/snowflake-arctic-embed-m-v1.5",
                    source_properties=["text", "title"],
                    vector_index_config=Configure.VectorIndex.hfresh(),
                )
            )
            client.collections.create(
                name,
                vector_config=vector_config,
                properties=[
                    Property(name=field, data_type=DataType.TEXT)
                    for field in (
                        "text",
                        "title",
                        "url",
                        "document_version",
                        "observed_at",
                        "dataset_id",
                    )
                ]
                + [Property(name="chunk_index", data_type=DataType.INT)],
            )
        collection = client.collections.get(name)
        if create and self._uses_vertex:
            ensure_named_vector(collection, self.settings.weaviate_vector_name)
        return collection

    def _fetch(self, url: str) -> tuple[str, str]:
        current = validate_source_url(url, self.settings.company_domain)
        with httpx.Client(timeout=20, follow_redirects=False) as client:
            for _ in range(4):
                with client.stream(
                    "GET", current, headers={"User-Agent": "CompanyCompass/0.1"}
                ) as response:
                    if response.is_redirect:
                        current = validate_source_url(
                            urljoin(current, response.headers["location"]),
                            self.settings.company_domain,
                        )
                        continue
                    response.raise_for_status()
                    if "text/html" not in response.headers.get("content-type", "").lower():
                        raise ValueError("Only HTML company pages are supported")
                    content = bytearray()
                    for piece in response.iter_bytes():
                        content.extend(piece)
                        if len(content) > MAX_BYTES:
                            raise ValueError("Company page exceeds the ingestion size limit")
                    soup = BeautifulSoup(bytes(content), "html.parser")
                    title = soup.title.get_text(" ", strip=True) if soup.title else current
                    for element in soup.select("script,style,nav,footer,header,noscript"):
                        element.decompose()
                    main = soup.find("main") or soup.find("article") or soup.body or soup
                    text = re.sub(r"\s+", " ", main.get_text(" ", strip=True))
                    if not text:
                        raise ValueError("Company page has no readable text")
                    return title[:250], text
        raise ValueError("Too many redirects")

    def _index_chunks(self, chunks: list[dict]) -> None:
        if self.settings.app_mode == "local":
            return
        from weaviate.classes.data import DataObject

        collection = self._collection(create=True)
        if self._uses_vertex:
            name, dimensions = (
                self.settings.weaviate_vector_name,
                self.settings.embedding_dimensions,
            )
            pending = [
                chunk
                for chunk in chunks
                if not valid_vector(stored_vector(collection, chunk_id(chunk), name), dimensions)
            ]
            if pending:
                vectors = self._embedder().embed_documents(pending)
                write_vectors(collection, pending, vectors, name, dimensions)
            verify_vectors(collection, chunks, name, dimensions)
            return
        objects = [
            DataObject(
                properties=chunk,
                uuid=chunk_id(chunk),
            )
            for chunk in chunks
        ]
        # A prior partial batch may already have staged some deterministic IDs.
        objects = [obj for obj in objects if not collection.data.exists(obj.uuid)]
        if not objects:
            return
        result = collection.data.insert_many(objects)
        if result.has_errors:
            raise ValueError("Some document chunks could not be indexed")

    def migrate_embeddings(self) -> dict:
        """Backfill and verify active chunks without changing content or provider settings."""
        if self.settings.app_mode != "cloud" or not self._uses_vertex:
            raise ValueError("Embedding migration requires cloud mode and the Vertex provider")
        name, dimensions = self.settings.weaviate_vector_name, self.settings.embedding_dimensions
        if dimensions != 1536:
            raise ValueError("This migration requires 1536-dimensional embeddings")
        with self._update_lock():
            documents = self._documents()
            chunks = [chunk for document in documents.values() for chunk in document["chunks"]]
            if len(chunks) > 500:
                raise ValueError("The assignment dataset is limited to 500 published chunks")
            try:
                collection = self._collection(create=True)
                vectors = self._embedder().embed_documents(chunks) if chunks else []
                write_vectors(collection, chunks, vectors, name, dimensions)
                verified = verify_vectors(collection, chunks, name, dimensions)
            except Exception:
                raise DocumentIndexingError(
                    "Embedding migration failed; existing content and provider are unchanged"
                ) from None
            return {
                "documents": len(documents),
                "embedded_chunks": len(chunks),
                "verified_chunks": verified,
                "vector_name": name,
                "dimensions": dimensions,
            }

    def _cleanup_chunks(self, old: list[dict], new: list[dict]) -> None:
        if self.settings.app_mode == "local" or not old:
            return
        collection = self._collection()
        if collection is not None:
            retained = {chunk_id(chunk) for chunk in new}
            for chunk in old:
                identity = chunk_id(chunk)
                if identity not in retained and collection.data.exists(identity):
                    if not collection.data.delete_by_id(identity):
                        raise RuntimeError("Obsolete chunk cleanup was not confirmed")

    def _write_document(
        self, url: str, title: str, content: str, source_kind: str, previous: dict | None
    ) -> tuple[dict, list[str], bool]:
        if previous and previous["title"] == title and previous["content"] == content:
            return previous, [], False
        document = make_document(url, title, content, source_kind, previous)
        published = sum(len(doc["chunks"]) for key, doc in self._documents().items() if key != url)
        if published + len(document["chunks"]) > 500:
            raise ValueError("The assignment dataset is limited to 500 published chunks")
        try:
            self._index_chunks(document["chunks"])
            self._publish(url, document)
        except Exception:
            raise DocumentIndexingError(
                "Could not index document; its previous published version is retained"
            ) from None
        warnings = []
        try:
            self._cleanup_chunks(previous["chunks"] if previous else [], document["chunks"])
        except Exception:
            warnings.append("Document published; obsolete vector cleanup must be retried later.")
        return document, warnings, True

    def fetch_evidence(self, url: str) -> dict:
        """Fetch an approved page for one answer without changing published knowledge."""
        approved = validate_source_url(url, self.settings.company_domain)
        title, text = self._fetch(approved)
        return {
            "title": title,
            "url": approved,
            "text": text,
            "observed_at": datetime.now(UTC).isoformat(),
            "source_kind": "official_web",
        }

    def ingest(self, urls: list[str]) -> dict:
        with self._update_lock():
            return self._ingest(urls)

    def _ingest(self, urls: list[str]) -> dict:
        if not 1 <= len(urls) <= 10:
            raise ValueError("Ingest between one and ten approved URLs per request")
        approved = list(
            dict.fromkeys(validate_source_url(url, self.settings.company_domain) for url in urls)
        )
        count, warnings = 0, []
        for url in approved:
            try:
                record = self._documents().get(url)
                previous = hydrate_document(url, record) if record else None
                if previous and previous["source_kind"] == "admin_edit":
                    warnings.append(
                        f"Skipped {url}: admin-edited content requires explicit replacement."
                    )
                    continue
                title, text = self._fetch(url)
                title, text = validate_edit(title, text, 1)
                _, cleanup_warnings, changed = self._write_document(
                    url, title, text, "official_web", previous
                )
                warnings.extend(cleanup_warnings)
                count += int(changed)
            except Exception:
                warnings.append(
                    f"Could not refresh {url}; its previous published evidence is retained."
                )
        return {"ingested": count, "warnings": warnings}

    def _query_cloud(self, query: str) -> list[dict]:
        from weaviate.classes.query import Filter

        versions = [doc["version"] for doc in self._documents().values()]
        if not versions:
            return []
        collection = self._collection()
        if collection is None:
            return []
        vector_options = {"target_vector": "default"}
        if self._uses_vertex:
            vector = self._embedder().embed_query(query)
            if not valid_vector(vector, self.settings.embedding_dimensions):
                raise ValueError("Query embedding dimension does not match the configured index")
            vector_options = {"target_vector": self.settings.weaviate_vector_name, "vector": vector}
        response = collection.query.hybrid(
            query=query,
            alpha=0.5,
            limit=40,
            filters=Filter.by_property("dataset_id").equal(DATASET)
            & Filter.by_property("document_version").contains_any(versions),
            **vector_options,
        )
        return [item.properties for item in response.objects]

    def search(self, query: str) -> dict:
        if not query.strip():
            return {"sources": [], "warnings": ["Enter a company question to search."]}
        documents = self._documents()
        warnings = []
        try:
            if self.settings.app_mode == "cloud":
                candidates = self._query_cloud(query)
            else:
                warnings.append("Local evidence uses lexical matching, not cloud hybrid retrieval.")
                terms = set(re.findall(r"\w+", query.lower()))
                candidates = [chunk for doc in documents.values() for chunk in doc["chunks"]]
                candidates = sorted(
                    candidates,
                    key=lambda chunk: len(terms & set(re.findall(r"\w+", chunk["text"].lower()))),
                    reverse=True,
                )
                candidates = [
                    chunk
                    for chunk in candidates
                    if terms & set(re.findall(r"\w+", chunk["text"].lower()))
                ]
            # Publication may have changed while the cloud query was running.
            documents = self._documents()
            sources = []
            for chunk in candidates:
                record = documents.get(chunk.get("url"))
                if not record or record.get("version") != chunk.get("document_version"):
                    continue
                document = hydrate_document(chunk["url"], record)
                sources.append(
                    {
                        **{key: chunk[key] for key in ("title", "url", "text", "observed_at")},
                        "url": document["source_url"] or "",
                        "document_id": document["id"],
                        "document_revision": document["revision"],
                        "source_kind": document["source_kind"],
                    }
                )
                if len(sources) == 4:
                    break
            if not sources:
                warnings.append(
                    "No published company evidence matched; ingest official pages first."
                )
            return {"sources": sources, "warnings": warnings}
        except Exception:
            return {
                "sources": [],
                "warnings": ["Company retrieval is unavailable; no facts were guessed."],
            }

    def check(self) -> bool:
        try:
            return self.settings.app_mode == "local" or self._connect().is_ready()
        except Exception:
            return False

    def close(self) -> None:
        if self.client is not None:
            self.client.close()
            self.client = None
