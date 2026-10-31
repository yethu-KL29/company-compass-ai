"""Explicit setup commands: connection checks never seed or ingest implicitly."""

import argparse
import asyncio
import json

from company_compass.core.container import catalog_service, close_catalog
from company_compass.core.settings import Settings
from company_compass.integrations.mcp_client import load_neo4j_tools
from company_compass.services.knowledge import KnowledgeService
from company_compass.utils.seed import load_demo_products


def check(settings: Settings):
    catalog = catalog_service(settings)
    knowledge = KnowledgeService(settings)
    result = {"mode": settings.app_mode, "model_configured": settings.model_configured}
    try:
        verify = getattr(catalog.repository, "verify_connectivity", None)
        if verify:
            verify()
        result["catalog_ready"] = True
    except Exception as error:
        result["catalog_ready"] = False
        result["catalog_error_type"] = type(error).__name__
    try:
        result["knowledge_ready"] = knowledge.check()
    except Exception as error:
        result["knowledge_ready"] = False
        result["knowledge_error_type"] = type(error).__name__
    finally:
        close_catalog(catalog)
        knowledge.close()
    print(json.dumps(result, indent=2))


def seed(settings: Settings):
    catalog = catalog_service(settings)
    try:
        initialize = getattr(catalog.repository, "initialize", None)
        if initialize:
            initialize()
        existing = {item.id for item in catalog.repository.list_products()}
        count = 0
        for product in load_demo_products():
            if product.id not in existing:
                catalog.publish(product, None)
                count += 1
        print(
            json.dumps(
                {
                    "created": count,
                    "preserved_existing": len(existing),
                    "mode": settings.app_mode,
                    "synthetic": True,
                }
            )
        )
    finally:
        close_catalog(catalog)


async def mcp_check(settings: Settings):
    tools = await load_neo4j_tools(settings)
    if not tools:
        print(json.dumps({"configured": False}))
        return
    native = {tool.name: tool for tool in tools}
    result = await native["get-schema"].ainvoke(
        {"type": "tool_call", "id": "check-schema", "name": "get-schema", "args": {}}
    )
    read_result = await native["read-cypher"].ainvoke(
        {
            "type": "tool_call",
            "id": "check-read",
            "name": "read-cypher",
            "args": {
                "query": "MATCH (c:Catalog {dataset_id:$dataset})-[:HAS_PRODUCT]->(p:Product) "
                "RETURN count(p) AS products",
                "params": {"dataset": "attoforce-demo-v1"},
            },
        }
    )
    print(
        json.dumps(
            {
                "configured": True,
                "tools": list(native),
                "schema_received": result.status == "success" and bool(result.content),
                "read_query_completed": read_result.status == "success",
                "read_only": "write-cypher" not in native,
            }
        )
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=[
            "serve",
            "check",
            "seed",
            "ingest",
            "mcp-check",
            "migrate-embeddings",
            "index-catalog",
        ],
    )
    parser.add_argument("urls", nargs="*")
    parser.add_argument("--port", type=int, default=8010, help="Local backend port")
    parser.add_argument("--local", action="store_true", help="Use explicit local synthetic storage")
    args = parser.parse_args()
    settings = Settings()
    if args.local:
        settings = settings.model_copy(update={"app_mode": "local"})
    try:
        if args.command == "serve":
            import uvicorn

            from company_compass.main import create_app

            uvicorn.run(create_app(settings), host="127.0.0.1", port=args.port)
        elif args.command == "check":
            check(settings)
        elif args.command == "seed":
            seed(settings)
        elif args.command == "mcp-check":
            asyncio.run(mcp_check(settings))
        elif args.command == "index-catalog":
            if settings.app_mode != "cloud":
                raise ValueError("Catalog hybrid indexes require cloud Neo4j mode")
            catalog = catalog_service(settings)
            try:
                catalog.repository.initialize_search()
                print(json.dumps(catalog.repository.reindex_search(), indent=2))
            finally:
                close_catalog(catalog)
        elif args.command == "migrate-embeddings":
            knowledge = KnowledgeService(
                settings.model_copy(update={"embedding_provider": "vertex"})
            )
            try:
                print(json.dumps(knowledge.migrate_embeddings(), indent=2))
            finally:
                knowledge.close()
        else:
            if not args.urls:
                parser.error("ingest requires at least one official company URL")
            knowledge = KnowledgeService(settings)
            try:
                print(json.dumps(knowledge.ingest(args.urls), indent=2))
            finally:
                knowledge.close()
    except Exception as error:
        # Deliberately avoid printing provider exception strings or environment values.
        print(
            json.dumps(
                {
                    "error": type(error).__name__,
                    "message": "Operation failed. Check configuration and service availability.",
                }
            )
        )
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
