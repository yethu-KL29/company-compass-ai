"""Semantic entry points into the current catalog, searched through native MCP.

Search text deliberately excludes prices and capacities. Those remain exact graph
facts for the agent to inspect after discovery, not semantic ranking signals.
"""

import asyncio
import json
import math
import re
from typing import Protocol

from company_compass.models.catalog import Product
from company_compass.repositories.catalog import DATASET_ID

VECTOR_INDEX = "catalog_product_vector"
FULLTEXT_INDEX = "catalog_product_fulltext"
SOURCE_K = 25
FINAL_K = 5

# Procedures retain compatibility with Neo4j 5 and newer databases. Each source is
# ranked independently; raw full-text and cosine scores are never added together.
HYBRID_QUERY = """
CALL {
  CALL db.index.vector.queryNodes('catalog_product_vector', $source_k, $query_vector)
  YIELD node AS p, score
  MATCH (:Catalog {dataset_id:$dataset})-[:HAS_PRODUCT]->(p)
        -[:CURRENT_REVISION]->(r:ProductRevision)
  WHERE p.status='active' AND r.status='published'
    AND p.search_model=$model AND p.search_dimensions=$dimensions
  WITH p, score ORDER BY score DESC, p.id ASC
  WITH collect(p) AS ranked
  UNWIND CASE WHEN size(ranked)=0 THEN [] ELSE range(0,size(ranked)-1) END AS rank
  RETURN ranked[rank] AS product, 1.0 / (60.0 + rank + 1) AS contribution
  UNION ALL
  CALL db.index.fulltext.queryNodes('catalog_product_fulltext', $lexical_query,
                                  {limit:$source_k})
  YIELD node AS p, score
  MATCH (:Catalog {dataset_id:$dataset})-[:HAS_PRODUCT]->(p)
        -[:CURRENT_REVISION]->(r:ProductRevision)
  WHERE p.status='active' AND r.status='published'
    AND p.search_model=$model AND p.search_dimensions=$dimensions
  WITH p, score ORDER BY score DESC, p.id ASC
  WITH collect(p) AS ranked
  UNWIND CASE WHEN size(ranked)=0 THEN [] ELSE range(0,size(ranked)-1) END AS rank
  RETURN ranked[rank] AS product, 1.0 / (60.0 + rank + 1) AS contribution
}
WITH product, sum(contribution) AS fused_score
ORDER BY fused_score DESC, product.id ASC
LIMIT $final_k
MATCH (product)-[:CURRENT_REVISION]->(r:ProductRevision)
WHERE product.status='active' AND r.status='published'
RETURN product.id AS product_id, fused_score, r.snapshot_json AS snapshot_json,
  {
    categories: [(r)-[:IN_CATEGORY]->(category:Category) | category.name],
    plans: [(r)-[:HAS_VARIANT]->(v:Variant) | {
      id: v.variant_id,
      name: v.name,
      max_users: v.max_users,
      use_cases: [(v)-[:SUPPORTS]->(task:UseCase) | task.name],
      capabilities: [(v)-[link:HAS_CAPABILITY]->(cap:Capability) |
                     {name: cap.name, availability: link.availability}],
      audiences: [(v)-[:FOR_AUDIENCE]->(audience:Audience) | audience.name],
      prices: [(v)-[:HAS_PRICE]->(offer:PriceOffer) | {
        amount_minor: offer.amount_minor, currency: offer.currency,
        billing_period: offer.billing_period, billing_unit: offer.billing_unit,
        price_type: offer.price_type
      }],
      attributes: [(v)-[:HAS_ATTRIBUTE]->(value:AttributeValue)
                     -[:DEFINED_BY]->(definition:AttributeDefinition) | {
        code: definition.code, value_state: value.value_state, unit: value.unit,
        text_value: value.text_value, integer_value: value.integer_value,
        number_value: value.number_value, data_type: definition.data_type,
        comparison_rule: definition.comparison_rule
      }],
      upgrades_to: [(v)-[:UPGRADES_TO]->(upgrade:Variant) | upgrade.variant_id],
      complements: [(v)-[:COMPLEMENTS]->(complement:Product) | complement.id]
    }]
  } AS relationship_context
ORDER BY fused_score DESC, product_id ASC
"""


class QueryEmbedder(Protocol):
    def embed_query(self, query: str) -> list[float]: ...


class ReadCypherTool(Protocol):
    async def ainvoke(self, arguments: dict) -> object: ...


def product_search_text(product: Product) -> str:
    """Deterministic product description and task vocabulary for both indexes."""
    use_cases = sorted(
        set(product.use_cases).union(*(set(plan.use_cases) for plan in product.plans))
    )
    readable = "; ".join(term.replace("_", " ") for term in use_cases)
    return f"Product: {product.name}\nDescription: {product.description}\nUse cases: {readable}"


def validate_vector(vector: object, dimensions: int) -> list[float]:
    """Reject malformed embeddings before sending data to an index or query."""
    if not isinstance(vector, (list, tuple)) or len(vector) != dimensions:
        raise ValueError("Catalog embedding dimension does not match the index")
    if any(type(value) not in (int, float) or not math.isfinite(value) for value in vector):
        raise ValueError("Catalog embedding must contain finite numbers")
    norm = math.hypot(*vector)
    if not norm or not math.isfinite(norm):
        raise ValueError("Catalog embedding must have a finite nonzero norm")
    return [float(value) for value in vector]


def lexical_query(text: str) -> str:
    """Quote words rather than accepting user-authored Lucene query operators."""
    words = list(dict.fromkeys(re.findall(r"[^\W_]+", text, flags=re.UNICODE)))[:64]
    return " OR ".join(f'"{word}"' for word in words)


def _native_rows(value: object) -> list[dict]:
    """Unwrap native LangChain/MCP text blocks without exposing provider errors."""
    if hasattr(value, "content"):
        if getattr(value, "status", "success") == "error":
            raise ValueError("Catalog MCP query failed")
        return _native_rows(value.content)
    if isinstance(value, str):
        return _native_rows(json.loads(value))
    if isinstance(value, dict):
        if "records" in value:
            return _native_rows(value["records"])
        raise ValueError("Catalog MCP response has no records")
    if isinstance(value, list):
        if value and all(
            isinstance(block, dict) and block.get("type") == "text" for block in value
        ):
            return [row for block in value for row in _native_rows(block["text"])]
        if all(isinstance(row, dict) for row in value):
            return value
    raise ValueError("Catalog MCP response has an unexpected shape")


class CatalogSearch:
    """Embed text, fuse lexical/vector ranks and return five current products."""

    def __init__(
        self,
        embeddings: QueryEmbedder,
        read_cypher: ReadCypherTool,
        *,
        model: str,
        dimensions: int,
    ):
        self.embeddings = embeddings
        self.read_cypher = read_cypher
        self.model = model
        self.dimensions = dimensions

    async def search(self, query: str) -> dict:
        evidence = {
            "products": [],
            "warnings": [],
            "retrieval": {"method": "hybrid_rrf", "limit": FINAL_K},
        }
        if not isinstance(query, str) or not 1 <= len(query.strip()) <= 2000:
            return {**evidence, "error": "Use a product requirement of 1 to 2000 characters"}
        query = query.strip()
        lexical = lexical_query(query)
        if not lexical:
            return {**evidence, "error": "Include words describing the product or use case"}
        try:
            vector = validate_vector(
                await asyncio.to_thread(self.embeddings.embed_query, query), self.dimensions
            )
            result = await self.read_cypher.ainvoke(
                {
                    "query": HYBRID_QUERY,
                    "params": {
                        "query_vector": vector,
                        "lexical_query": lexical,
                        "dataset": DATASET_ID,
                        "source_k": SOURCE_K,
                        "final_k": FINAL_K,
                        "model": self.model,
                        "dimensions": self.dimensions,
                    },
                }
            )
            products = []
            seen = set()
            for row in _native_rows(result):
                product = Product.model_validate_json(row["snapshot_json"])
                if product.id != row["product_id"] or product.status != "active":
                    raise ValueError("Catalog search returned inconsistent product data")
                score = row["fused_score"]
                if type(score) not in (int, float) or not math.isfinite(score) or score < 0:
                    raise ValueError("Catalog search returned an invalid ranking")
                context = row["relationship_context"]
                if (
                    not isinstance(context, dict)
                    or not isinstance(context.get("categories"), list)
                    or not isinstance(context.get("plans"), list)
                ):
                    raise ValueError("Catalog search did not return graph relationship context")
                if product.id not in seen and len(products) < FINAL_K:
                    products.append(
                        {
                            "score": float(score),
                            "product": product.model_dump(),
                            "relationship_context": context,
                        }
                    )
                    seen.add(product.id)
            return {**evidence, "products": products}
        except Exception:
            # Neither embedding vectors nor database/provider exception text is
            # evidence. Keep failures distinguishable from a genuine empty match.
            return {
                **evidence,
                "error": "Catalog hybrid search is unavailable; retry or inspect its indexes",
            }
