"""Small local and Neo4j repositories with optimistic revision publication."""

import json
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from typing import Protocol
from uuid import uuid4

from company_compass.models.catalog import ATTRIBUTE_DEFINITIONS, Product
from company_compass.utils.storage import atomic_write_json

DATASET_ID = "attoforce-demo-v1"
_LOCAL_LOCK = RLock()


class RevisionConflict(ValueError):
    """A submitted edit was based on a superseded catalog revision."""


class CatalogRepository(Protocol):
    def list_products(self) -> list[Product]: ...
    def get_product(self, product_id: str) -> Product | None: ...
    def publish(self, product: Product, expected_revision: int | None) -> Product: ...


class LocalCatalogRepository:
    """Atomic JSON snapshots for the single-process local assignment mode."""

    def __init__(self, path: Path):
        self.path = Path(path)

    def _load(self):
        if not self.path.exists():
            return {"catalog_version": 0, "products": {}, "history": []}
        return json.loads(self.path.read_text(encoding="utf-8"))

    def list_products(self) -> list[Product]:
        with _LOCAL_LOCK:
            return [Product.model_validate(value) for value in self._load()["products"].values()]

    def get_product(self, product_id: str) -> Product | None:
        return next((product for product in self.list_products() if product.id == product_id), None)

    def publish(self, product: Product, expected_revision: int | None = None) -> Product:
        with _LOCAL_LOCK:
            state = self._load()
            previous = state["products"].get(product.id)
            actual = previous["revision"] if previous else None
            if actual != expected_revision:
                raise RevisionConflict("Catalog changed; reload the product before publishing")
            published = product.model_copy(update={"revision": (actual or 0) + 1}, deep=True)
            state["catalog_version"] += 1
            state["products"][product.id] = published.model_dump()
            state["history"].append(
                {"product": published.model_dump(), "published_at": datetime.now(UTC).isoformat()}
            )
            atomic_write_json(self.path, state)
            return published


class Neo4jCatalogRepository:
    """Neo4j is authoritative. Immutable revision JSON also preserves DTO fidelity."""

    def __init__(
        self,
        uri: str,
        username: str,
        password: str,
        database: str,
        *,
        embedding_client=None,
        embedding_model: str = "",
        embedding_dimensions: int = 1536,
    ):
        from neo4j import GraphDatabase

        self.driver = GraphDatabase.driver(uri, auth=(username, password))
        self.database = database
        self.embeddings = embedding_client
        self.embedding_model = embedding_model
        self.embedding_dimensions = embedding_dimensions

    def close(self):
        self.driver.close()

    def verify_connectivity(self):
        self.driver.verify_connectivity()

    def initialize(self):
        """Explicit, idempotent schema setup; never performed during user queries."""
        constraints = {
            "catalog_dataset": ("Catalog", "dataset_id"),
            "product_key": ("Product", "storage_key"),
            "revision_key": ("ProductRevision", "revision_id"),
            "variant_key": ("Variant", "variant_node_id"),
        }
        with self.driver.session(database=self.database) as session:
            for name, (label, field) in constraints.items():
                session.run(
                    f"CREATE CONSTRAINT {name} IF NOT EXISTS "
                    f"FOR (n:{label}) REQUIRE n.{field} IS UNIQUE"
                ).consume()

    def initialize_search(self):
        """Explicit index setup, separate from request-time reads and writes."""
        with self.driver.session(database=self.database) as session:
            session.run(
                "CREATE VECTOR INDEX catalog_product_vector IF NOT EXISTS "
                "FOR (p:Product) ON p.search_embedding OPTIONS {indexConfig: {"
                "`vector.dimensions`: $dimensions, `vector.similarity_function`: 'cosine'}}",
                dimensions=self.embedding_dimensions,
            ).consume()
            session.run(
                "CREATE FULLTEXT INDEX catalog_product_fulltext IF NOT EXISTS "
                "FOR (p:Product) ON EACH [p.search_text]"
            ).consume()
            session.run("CALL db.awaitIndexes(30)").consume()
            row = session.run(
                "SHOW VECTOR INDEXES YIELD name, options "
                "WHERE name='catalog_product_vector' RETURN options"
            ).single()
            if (
                not row
                or row["options"]["indexConfig"]["vector.dimensions"] != self.embedding_dimensions
            ):
                raise ValueError(
                    "Catalog vector index dimensions differ; explicit migration required"
                )

    def _search_payload(self, product: Product) -> dict:
        from company_compass.services.catalog_search import product_search_text, validate_vector

        if product.status != "active":
            return {
                "search_text": None,
                "search_embedding": None,
                "search_model": None,
                "search_dimensions": None,
            }
        if self.embeddings is None:
            raise ValueError("Catalog embedding provider is not configured")
        text = product_search_text(product)
        vectors = self.embeddings.embed_documents([{"title": product.name, "text": text}])
        if len(vectors) != 1:
            raise ValueError("Catalog embedding provider returned an unexpected batch")
        validate_vector(vectors[0], self.embedding_dimensions)
        return {
            "search_text": text,
            "search_embedding": vectors[0],
            "search_model": self.embedding_model,
            "search_dimensions": self.embedding_dimensions,
        }

    def reindex_search(self) -> dict:
        """Backfill current products without changing their publication revisions."""
        indexed, skipped = 0, 0
        for product in self.list_products():
            payload = self._search_payload(product)
            with self.driver.session(database=self.database) as session:
                # Lock this same catalog counter used by publication, then recheck
                # revision in a second statement to avoid publishing stale vectors.
                def update(tx, product=product, payload=payload):
                    tx.run(
                        "MATCH (c:Catalog {dataset_id:$dataset}) "
                        "SET c.catalog_version=c.catalog_version",
                        dataset=DATASET_ID,
                    ).consume()
                    return tx.run(
                        "MATCH (:Catalog {dataset_id:$dataset})-[:HAS_PRODUCT]->(p:Product)"
                        "-[:CURRENT_REVISION]->(r:ProductRevision) "
                        "WHERE p.id=$id AND r.revision_number=$revision "
                        "SET p += $search RETURN count(p) AS updated",
                        dataset=DATASET_ID,
                        id=product.id,
                        revision=product.revision,
                        search=payload,
                    ).single()

                row = session.execute_write(update)
                if row and row["updated"]:
                    indexed += 1
                else:
                    skipped += 1
        return {
            "indexed": indexed,
            "skipped_concurrent_updates": skipped,
            "dimensions": self.embedding_dimensions,
            "model": self.embedding_model,
        }

    def list_products(self) -> list[Product]:
        for _ in range(2):
            with self.driver.session(database=self.database) as session:
                result = session.execute_read(self._read_snapshot)
            if result is not None:
                return result
        raise RevisionConflict("Catalog changed during retrieval; please retry")

    @staticmethod
    def _read_snapshot(tx):
        row = tx.run(
            "MATCH (c:Catalog {dataset_id:$dataset}) RETURN c.catalog_version AS version",
            dataset=DATASET_ID,
        ).single()
        if row is None:
            return []
        version = row["version"]
        records = list(
            tx.run(
                """
            MATCH (:Catalog {dataset_id:$dataset})-[:HAS_PRODUCT]->(p:Product)
                  -[:CURRENT_REVISION]->(r:ProductRevision)
            WHERE r.status = 'published'
            RETURN r.snapshot_json AS snapshot ORDER BY p.id
        """,
                dataset=DATASET_ID,
            )
        )
        after = tx.run(
            "MATCH (c:Catalog {dataset_id:$dataset}) RETURN c.catalog_version AS version",
            dataset=DATASET_ID,
        ).single()["version"]
        if version != after:
            return None
        return [Product.model_validate_json(record["snapshot"]) for record in records]

    def get_product(self, product_id: str) -> Product | None:
        return next((product for product in self.list_products() if product.id == product_id), None)

    def publish(self, product: Product, expected_revision: int | None = None) -> Product:
        search = self._search_payload(product) if self.embeddings is not None else None
        with self.driver.session(database=self.database) as session:
            return session.execute_write(self._publish, product, expected_revision, search)

    @staticmethod
    def _publish(tx, product, expected_revision, search=None):
        # Lock the shared catalog counter before checking/changing current pointers.
        tx.run(
            """
            MERGE (c:Catalog {dataset_id:$dataset})
            ON CREATE SET c.catalog_version=0, c.is_synthetic=true, c.ontology_version='1'
            SET c.catalog_version=c.catalog_version
            MERGE (company:Company {id:'attoforce'})
            MERGE (company)-[:HAS_CATALOG]->(c)
        """,
            dataset=DATASET_ID,
        ).consume()
        key = f"{DATASET_ID}:{product.id}"
        previous = tx.run(
            """
            MATCH (p:Product {storage_key:$key})-[:CURRENT_REVISION]->(r:ProductRevision)
            RETURN r.revision_number AS revision
        """,
            key=key,
        ).single()
        actual = previous["revision"] if previous else None
        if actual != expected_revision:
            raise RevisionConflict("Catalog changed; reload the product before publishing")
        published = product.model_copy(update={"revision": (actual or 0) + 1}, deep=True)
        revision_id = str(uuid4())
        tx.run(
            """
            MATCH (c:Catalog {dataset_id:$dataset})
            MERGE (p:Product {storage_key:$key})
            SET p.id=$id, p.status=$status, p.is_synthetic=true, p.dataset_id=$dataset
            MERGE (c)-[:HAS_PRODUCT]->(p)
            CREATE (r:ProductRevision {revision_id:$revision_id, revision_number:$revision,
                status:'published', name:$name, description:$description,
                snapshot_json:$snapshot, published_at:datetime()})
            CREATE (p)-[:HAS_REVISION]->(r)
            WITH c,p,r
            OPTIONAL MATCH (p)-[old:CURRENT_REVISION]->()
            DELETE old
            WITH DISTINCT c,p,r
            CREATE (p)-[:CURRENT_REVISION]->(r)
            SET c.catalog_version=c.catalog_version+1
            CREATE (e:ChangeEvent {event_id:$event_id, action:'publish', actor_id:'admin',
                timestamp:datetime(), catalog_version:c.catalog_version})
            CREATE (e)-[:CHANGED]->(p)
            CREATE (e)-[:RESULTED_IN]->(r)
            MERGE (s:Source {source_id:'synthetic-demo'})
            SET s.source_kind='synthetic_admin', s.label='Fictional assignment catalog'
            CREATE (r)-[:SUPPORTED_BY]->(s)
        """,
            dataset=DATASET_ID,
            key=key,
            id=published.id,
            status=published.status,
            revision_id=revision_id,
            revision=published.revision,
            name=published.name,
            description=published.description,
            snapshot=published.model_dump_json(),
            event_id=str(uuid4()),
        ).consume()
        for category in published.categories:
            tx.run(
                """
                MATCH (r:ProductRevision {revision_id:$revision})
                MERGE (c:Category {dataset_id:$dataset, name:$name})
                CREATE (r)-[:IN_CATEGORY]->(c)
            """,
                revision=revision_id,
                dataset=DATASET_ID,
                name=category,
            ).consume()
        for plan in published.plans:
            Neo4jCatalogRepository._write_plan(tx, revision_id, published, plan)
        for plan in published.plans:
            tx.run(
                """
                MATCH (v:Variant {variant_node_id:$node_id})
                UNWIND $targets AS target
                MATCH (next:Variant {variant_node_id:target})
                CREATE (v)-[:UPGRADES_TO]->(next)
            """,
                node_id=f"{revision_id}:{plan.id}",
                targets=[f"{revision_id}:{target}" for target in plan.upgrades_to],
            ).consume()
            for complement in published.complements:
                tx.run(
                    """
                    MATCH (v:Variant {variant_node_id:$node_id})
                    MERGE (p:Product {storage_key:$target_key})
                    ON CREATE SET p.id=$target_id, p.dataset_id=$dataset, p.is_synthetic=true
                    CREATE (v)-[:COMPLEMENTS]->(p)
                """,
                    node_id=f"{revision_id}:{plan.id}",
                    target_key=f"{DATASET_ID}:{complement}",
                    target_id=complement,
                    dataset=DATASET_ID,
                ).consume()
        tx.run(
            "MATCH (p:Product {storage_key:$key}) SET p += $search",
            key=key,
            search=search
            or {
                "search_text": None,
                "search_embedding": None,
                "search_model": None,
                "search_dimensions": None,
            },
        ).consume()
        return published

    @staticmethod
    def _write_plan(tx, revision_id, product, plan):
        node_id = f"{revision_id}:{plan.id}"
        tx.run(
            """
            MATCH (r:ProductRevision {revision_id:$revision})
            CREATE (v:Variant {variant_node_id:$node_id, variant_id:$id,
                name:$name, max_users:$max_users})
            CREATE (r)-[:HAS_VARIANT]->(v)
            CREATE (o:PriceOffer {offer_id:$offer_id, amount_minor:$amount, currency:$currency,
                billing_period:$period, billing_unit:$unit, price_type:$price_type,
                observed_at:datetime()})
            CREATE (v)-[:HAS_PRICE]->(o)
            WITH v,o
            MATCH (s:Source {source_id:'synthetic-demo'})
            CREATE (o)-[:SUPPORTED_BY]->(s)
        """,
            revision=revision_id,
            node_id=node_id,
            id=plan.id,
            name=plan.name,
            max_users=plan.max_users,
            offer_id=str(uuid4()),
            amount=plan.price_minor,
            currency=plan.currency,
            period=plan.billing_period,
            unit=plan.billing_unit,
            price_type="fixed" if plan.price_minor is not None else "quote_only",
        ).consume()
        # Labels below are application constants, never interpolated user input.
        for relation, label, values in [
            ("HAS_CAPABILITY", "Capability", plan.capabilities),
            ("SUPPORTS", "UseCase", plan.use_cases or product.use_cases),
            ("FOR_AUDIENCE", "Audience", plan.audiences or product.audiences),
        ]:
            tx.run(
                f"""
                MATCH (v:Variant {{variant_node_id:$node_id}})
                UNWIND $values AS name
                MERGE (n:{label} {{dataset_id:$dataset, name:name}})
                CREATE (v)-[:{relation} {{availability:'included'}}]->(n)
            """,
                node_id=node_id,
                dataset=DATASET_ID,
                values=values,
            ).consume()
        for code, value in plan.attributes.items():
            definition = ATTRIBUTE_DEFINITIONS[code]
            field = {"text": "text_value", "integer": "integer_value", "number": "number_value"}[
                definition["data_type"]
            ]
            tx.run(
                """
                MATCH (v:Variant {variant_node_id:$node_id})
                MERGE (d:AttributeDefinition {dataset_id:$dataset, code:$code})
                ON CREATE SET d.data_type=$data_type, d.canonical_unit=$unit,
                    d.comparison_rule=$comparison_rule, d.semantic_version='1'
                CREATE (a:AttributeValue {attribute_value_id:$value_id,
                    value_state:'known', unit:$unit})
                SET a += $typed_value
                CREATE (v)-[:HAS_ATTRIBUTE]->(a)
                CREATE (a)-[:DEFINED_BY]->(d)
            """,
                node_id=node_id,
                dataset=DATASET_ID,
                code=code,
                typed_value={field: value},
                data_type=definition["data_type"],
                unit=definition["canonical_unit"],
                comparison_rule=definition["comparison_rule"],
                value_id=str(uuid4()),
            ).consume()
