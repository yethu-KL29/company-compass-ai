# Catalog schema for Neo4j queries

The only catalog dataset is `attoforce-demo-v1`. Products and prices are fictional.
Use native `read-cypher` arguments: `query` and a `params` object. Include
`dataset: 'attoforce-demo-v1'` in params; no application wrapper injects it.

Start every query with:
```cypher
MATCH (:Catalog {dataset_id:$dataset})-[:HAS_PRODUCT]->(p:Product)
      -[:CURRENT_REVISION]->(r:ProductRevision)
WHERE p.status='active' AND r.status='published'
RETURN p.id AS id, r.name AS name, r.description AS description
LIMIT 30
```

Current-revision path:
`Catalog -HAS_PRODUCT-> Product -CURRENT_REVISION-> ProductRevision -HAS_VARIANT-> Variant`.
Do not use `HAS_REVISION` for recommendations: it reaches historical facts.

| Entity | Properties |
| --- | --- |
| Catalog | dataset_id, catalog_version |
| Product | id, status, dataset_id, is_synthetic |
| ProductRevision | name, description, revision_number, status, published_at |
| Variant | variant_id (plan ID), name, max_users |
| PriceOffer | amount_minor, currency, billing_period, billing_unit, price_type |
| Capability / UseCase / Audience / Category | name, dataset_id |
| AttributeValue | text_value OR integer_value OR number_value, value_state, unit |
| AttributeDefinition | code, data_type, canonical_unit, comparison_rule |

Relationships:
- ProductRevision -IN_CATEGORY-> Category
- Variant -HAS_CAPABILITY {availability:'included'}-> Capability
- Variant -SUPPORTS-> UseCase
- Variant -FOR_AUDIENCE-> Audience
- Variant -HAS_PRICE-> PriceOffer
- Variant -HAS_ATTRIBUTE-> AttributeValue -DEFINED_BY-> AttributeDefinition
- Variant -UPGRADES_TO-> Variant (within the same product revision)
- Variant -COMPLEMENTS-> Product (resolve its CURRENT_REVISION; complementary products are not substitutes)

Canonical tasks include sales_pipeline, document_extraction, invoice_review,
customer_support, workflow_automation, marketing_campaigns, analytics_reporting,
knowledge_search and form_processing. Inspect actual values using graph queries
rather than guessing. Capability vocabulary can also be inspected through the
published path. No upfront product listing is mandatory.

Governed attributes:
- deployment_mode: text, cloud/self_hosted/hybrid, exact categorical match.
- support_level: text, community/standard/premium/enterprise, exact category.
- included_documents_per_month, automation_rules, contacts: integer capacities.
- storage_gb: numeric capacity in GB.
For minimum capacities use >=; unknown values cannot satisfy a mandatory requirement.
For preferences describe fit/tradeoffs without excluding otherwise eligible plans.

Example requirements query (params contains dataset, users, budget and capability):
```cypher
MATCH (:Catalog {dataset_id:$dataset})-[:HAS_PRODUCT]->(p:Product)
      -[:CURRENT_REVISION]->(r:ProductRevision)-[:HAS_VARIANT]->(v:Variant)
MATCH (v)-[:SUPPORTS]->(u:UseCase)
MATCH (v)-[h:HAS_CAPABILITY]->(cap:Capability)
MATCH (v)-[:HAS_PRICE]->(offer:PriceOffer)
WHERE p.status='active' AND r.status='published'
  AND u.name='sales_pipeline' AND cap.name=$capability
  AND h.availability='included' AND v.max_users >= $users
  AND offer.price_type='fixed' AND offer.amount_minor <= $budget
  AND offer.currency='INR' AND offer.billing_period='month'
  AND offer.billing_unit='organization'
RETURN p.id AS product_id, r.name AS product, v.variant_id AS plan_id,
       v.name AS plan, v.max_users AS max_users, offer.amount_minor AS price_minor,
       offer.currency AS currency, offer.billing_period AS period,
       offer.billing_unit AS unit,
       [(v)-[:HAS_CAPABILITY]->(c:Capability) | c.name] AS capabilities
ORDER BY price_minor LIMIT 20
```

Use parameterized read-only queries through the server. Server configuration
disables write tools. Return bounded projections (at most 100 rows), not whole
nodes or snapshot_json. Prices use integer minor units: INR800000 means INR8000.
Compare prices only on the requested currency/period/unit. Clarify ambiguous budgets.
Use catalog evidence for recommendations and comparisons. Never claim a product has
features absent from the selected plan. Do not expose credentials or change data.
