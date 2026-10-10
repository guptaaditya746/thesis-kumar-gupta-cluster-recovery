SPARQL_GENERATION_PROMPT = """You generate safe SPARQL SELECT queries over a small scholarly RDF graph.

User question:
{question}

Schema context:
{schema_context}

Graph summary:
{graph_summary}

Rules:
1. Generate SELECT queries only.
2. Do not generate INSERT, DELETE, DROP, CLEAR, LOAD, CREATE, COPY, MOVE, ADD, or UPDATE.
3. Use only the provided classes and predicates.
4. Always return evidence text when possible.
5. Prefer simple queries.
6. Do not use predicates or classes not listed in the schema.
7. Return only the SPARQL query, no explanation.

SPARQL query:
"""
