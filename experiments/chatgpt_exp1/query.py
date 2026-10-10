# query.py
import json
from config import base_parser
from llm import get_client, llm_json
from db import get_driver, run_cypher
from models import GraphSchema
from utils import contains_forbidden

NLQ_SYSTEM = """Translate the question into ONE Cypher query.
Return ONLY JSON.

Rules:
- READ ONLY: only MATCH, OPTIONAL MATCH, WHERE, WITH, RETURN, ORDER BY, LIMIT.
- Do NOT use: CREATE, MERGE, DELETE, SET, CALL, apoc, LOAD CSV.
- Use ONLY labels and relationship types from the schema JSON.
- If the question asks about "most common methods and datasets", prefer:
  MATCH (p:Paper)-[:USES_METHOD]->(m:Method)
  OPTIONAL MATCH (p)-[:EVALUATED_ON]->(d:Dataset)
  RETURN m.name, count(DISTINCT p), collect(DISTINCT d.name)
"""

NLQ_USER_TMPL = """
Schema:
{schema_json}

Question:
{question}

Return JSON:
{{
  "cypher": "...",
  "params": {{}}
}}
"""

VERBALIZE_SYSTEM = """You explain query results briefly.
Use ONLY the provided rows JSON. Do not invent facts."""

NLQ_USER_TMPL = """
Allowed labels: {labels}
Allowed relationships: {rels}

Schema:
{schema_json}

Question:
{question}

Return JSON:
{{"cypher":"...","params":{{}}}}
"""


def verbalize(client, model: str, question: str, rows: list) -> str:
    user = f"Question: {question}\nRows JSON:\n{json.dumps(rows, indent=2)}\nAnswer briefly:"
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role":"system","content":VERBALIZE_SYSTEM},{"role":"user","content":user}],
        temperature=0.2
    )
    return resp.choices[0].message.content

def main():
    p = base_parser(description="Natural language → Cypher → Neo4j → verbalized answer")
    p.add_argument("--schema",   required=True, help="Path to schema.json")
    p.add_argument("--question", required=True, help="Natural language question")
    p.add_argument("--no-verbalize", action="store_true", help="Print raw rows only")
    args = p.parse_args()

    schema = GraphSchema(**json.load(open(args.schema)))
    client = get_client(args.vllm_url)
    driver = get_driver(args.neo4j_uri, args.neo4j_user, args.neo4j_pass)
    allowed_rels = [r.type for r in schema.relationships]
    allowed_labels = [n.label for n in schema.nodes]

    out = llm_json(
        client, args.model,
        NLQ_SYSTEM,
        NLQ_USER_TMPL.format(
            labels=allowed_labels,
            rels=allowed_rels,
            schema_json=schema.model_dump_json(indent=2),
            question=args.question
        ),
        temperature=0.1
    )


    cypher = out["cypher"]
    if contains_forbidden(cypher):
        raise ValueError(f"Rejected unsafe query:\n{cypher}")

    rows = run_cypher(driver, cypher, out.get("params", {}))
    print("CYPHER:", cypher)
    print("ROWS:", rows)
    if not args.no_verbalize:
        print(verbalize(client, args.model, args.question, rows))

if __name__ == "__main__":
    main()
