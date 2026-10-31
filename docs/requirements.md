# Requirements and open decisions

Updated: 2026-10-31

## Confirmed brief

Build an AI assistant using a framework of our choice and MCP that:

1. Answers customers' questions about a company.
2. Recommends products based on customers' requirements.

The user requested brainstorming, research, planning, architecture, and stack selection before implementation. Store substantive project notes in this repository for future reference.

## Confirmed company and knowledge scope

The user confirmed one fixed company. Company selection remains open; support for multiple or arbitrary companies is outside the present scope.

The user proposed a knowledge management system with:

- Hybrid RAG for company answers, now under evaluation after the user asked whether it is needed.
- An MCP server for searching/scraping data during ingestion.
- A daily pipeline to discover recent company updates and automatically ingest relevant changes.

The architecture adopts fixed-company knowledge management and daily MCP ingestion. Hybrid retrieval is a proposed technique, not a mandatory requirement. Exact providers, retrieval strategy, schedule/timezone, source rules, and deployment remain proposals. No actual daily job has been created.

## Product recommendation interpretation

The user asked whether recommendations refer to the chosen company's products or arbitrary products. Recommended interpretation of the original brief: recommend products offered by the fixed company, based on customer requirements. This is an interpretation to discuss, not an explicit statement from the brief's author. Cross-company shopping is additional scope.

For a retailer, "company products" can include the assortment it sells, including other manufacturers. For a manufacturer, use its own catalog. For a service company, offerings or plans may be the equivalent; confirm suitability when choosing the company.

## Proposals awaiting clarification

- IKEA India was explored as a candidate, with home-office desks and chairs as a manageable first catalog. It has not been selected by the user.
- English and INR are proposed only for that candidate and market.
- A local-first, evaluable MVP was proposed as a starting point; production readiness is not assumed.
- A daily refreshed catalog with observation timestamps is proposed. Daily refresh does not establish real-time pricing or stock; live checks remain an open requirement.

## Other open questions

- Assignment, interview, portfolio project, or product? What are the evaluation criteria?
- Deadline and expected deliverables: code, deployed demo, documentation, video, or presentation?
- Preferred languages, frameworks, hosting, and paid API budget?
- Required company-question coverage: overview, policies, services, locations, or other topics?
- Must prices, inventory, delivery eligibility, or other facts be live?
- Is customer authentication or persistent conversation history required?

The fixed-company scope has been answered. Company identity, delivery level, evaluation, deadline, budget, and runtime constraints remain open.
