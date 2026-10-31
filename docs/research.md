# Initial research

Research date: 2026-10-31. Sources below are official documentation or company pages. Findings inform proposals; they do not establish user requirements. Recheck changing APIs and company information before implementation.

## Company candidate and data

IKEA India offers public company-support and product pages suitable for exploring both requested use cases. Its desk listing and a sampled product page expose useful catalog attributes. The sampled LINNMON / ADILS page includes dimensions, materials, and suitability restrictions. This suggests recommendations should consider explicit product constraints rather than rely only on semantic similarity.

- [IKEA India desks](https://www.ikea.com/in/en/cat/desks-computer-desks-20649/)
- [Sample product](https://www.ikea.com/in/en/p/linnmon-adils-table-white-s09246408/)
- [IKEA India FAQ](https://www.ikea.com/in/en/customer-service/faq-pub7f08ed41/)
- [IKEA India return policy](https://www.ikea.com/in/en/customer-service/returns-claims/return-policy/)

Observed conflict: the FAQ describes a 90-day mattress exchange period, while the dedicated policy describes 365 days. Proposed handling: track source authority, market, and retrieval date; prioritize the dedicated policy for that topic and flag unresolved conflicts. Avoid merging policies from different countries. These observations are research examples, not application seed data or customer advice.

Public readability does not establish permission for bulk extraction or redistribution. Prefer a small curated factual dataset with links; assess source terms before automating ingestion. No official IKEA integration, stock API, or authorization has been established.

## Framework and MCP

[LangGraph](https://docs.langchain.com/oss/python/langgraph/overview) supports stateful workflows combining deterministic and model-driven steps and does not require using LangChain. It is a candidate for explicit routing, clarification, retrieval, recommendation, and validation stages.

[LlamaIndex](https://developers.llamaindex.ai/python/framework/) is an alternative to assess if document ingestion and retrieval become the dominant requirements. Framework preference remains a design judgment, not a benchmark result.

[MCP architecture](https://modelcontextprotocol.io/docs/learn/architecture) separates the host application, clients, and servers. Proposed application mapping: the backend hosts the assistant and an MCP client; a project-owned MCP server exposes company knowledge and catalog operations. MCP is the integration protocol; retrieval and recommendation logic still need implementation.

The [official Python SDK](https://py.sdk.modelcontextprotocol.io/) currently documents stable v2 and Python 3.11+. Its [transport guide](https://py.sdk.modelcontextprotocol.io/run/) supports local stdio and deployed Streamable HTTP. Avoid mixing v1 examples with v2 imports. Use SDK negotiation rather than manually implementing protocol messages.

[LangChain's MCP integration](https://docs.langchain.com/oss/python/langchain/mcp) currently documents `MCPAdapter` under a beta namespace and migration from older adapters. Proposed preference: use the official MCP SDK directly inside LangGraph nodes unless an adapter demonstrably simplifies the implementation. Verify compatible versions in a small protocol spike.

[MCP security guidance](https://modelcontextprotocol.io/specification/latest/basic/security_best_practices) informs endpoint trust, authorization, and data-boundary design. Proposed MVP tools are read-only, with validated inputs and no arbitrary SQL, URLs, or shell execution.

## Model integration

Official OpenAI documentation was consulted using the OpenAI Docs skill:

- [Responses API](https://developers.openai.com/api/reference/responses/overview)
- [Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs)
- [Model catalog](https://developers.openai.com/api/docs/models)
- [GPT-6.1 Sol](https://developers.openai.com/api/docs/models/gpt-6.1-sol)
- [Text embedding model](https://developers.openai.com/api/docs/models/text-embedding-3-small)

Responses supports application integrations through function calling. Structured Outputs can constrain response shape, but factual grounding still requires application validation. Proposed provider is OpenAI behind a small adapter, subject to API budget and account access. GPT-6.1 Sol is a possible initial evaluation baseline, not a mandatory or cost-optimal selection. No live model calls or benchmarks were performed.

An older GPT-5 Mini candidate was investigated; its [model page](https://developers.openai.com/api/docs/models/gpt-5-mini) currently labels its alias/snapshot deprecated. It is not the proposed baseline. No paid API calls were needed for this research.

## Application and storage candidates

- [FastAPI features](https://fastapi.tiangolo.com/features/): candidate Python API layer with typed validation and generated API documentation.
- [PostgreSQL full-text search](https://www.postgresql.org/docs/current/textsearch.html): candidate lexical retrieval alongside structured catalog filters.
- [pgvector](https://github.com/pgvector/pgvector): vector similarity search in the same database; avoids a separate vector service for an MVP.
- [React app guidance](https://react.dev/learn/creating-a-react-app) and [Vite](https://vite.dev/guide/): a React/TypeScript SPA is a candidate for a chat interface backed by a separate Python API. React generally recommends frameworks; a Vite SPA is a deliberate simplicity tradeoff when server rendering is unnecessary.

No dependency versions have been installed or locked. Verify current stable, mutually compatible versions during scaffolding.

## Follow-up: automated ingestion and Perplexity

The user confirmed a fixed company and proposed hybrid RAG with daily MCP-based web ingestion. Reviewed [Perplexity's crawler documentation](https://docs.perplexity.ai/docs/resources/perplexity-crawlers) and [Pro Search explanation](https://www.perplexity.ai/help-center/en/articles/10352903-what-is-pro-search): background indexing, query-triggered page visits, source synthesis, and citations are documented. These sources do not verify a specific internal vector database design.

Reviewed [Firecrawl MCP](https://docs.firecrawl.dev/mcp-server) as an existing search/scrape server candidate and [Firecrawl change tracking](https://docs.firecrawl.dev/features/change-tracking) for incremental refresh. Endpoint tool availability and change-tracking exposure through MCP require a practical spike. No scraper connection, account, purchase, or scraping job was created. Detailed design is in [ingestion and retrieval](ingestion-and-retrieval.md).

## Follow-up: is hybrid retrieval necessary?

Reviewed [PostgreSQL full-text search introduction](https://www.postgresql.org/docs/current/textsearch-intro.html) and [pgvector documentation](https://github.com/pgvector/pgvector). They establish available lexical/vector capabilities, not a measured advantage for this project's unselected corpus. Recommendation: compare retrieval variants on representative queries before treating hybrid as necessary. Exact product identifiers and numerical constraints need appropriate structured lookups/filters.
