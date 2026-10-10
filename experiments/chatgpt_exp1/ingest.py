# ingest.py
import json
from config import base_parser
from llm import get_client, llm_json
from db import get_driver, ensure_constraints, upsert_extraction
from models import GraphSchema, Extraction
from extract import extract_from_text   # logic from notebook cell

def main():
    p = base_parser(description="Extract entities from text and ingest into Neo4j")
    p.add_argument("--schema", required=True, help="Path to schema.json")
    p.add_argument("--docs",   required=True, nargs="+", help="Text strings or @file.txt paths")
    args = p.parse_args()

    schema = GraphSchema(**json.load(open(args.schema)))
    client = get_client(args.vllm_url)
    driver = get_driver(args.neo4j_uri, args.neo4j_user, args.neo4j_pass)
    ensure_constraints(driver, schema)

    for raw in args.docs:
        text = open(raw[1:]).read() if raw.startswith("@") else raw
        ex = extract_from_text(client, args.model, text, schema)
        upsert_extraction(driver, ex, schema)
        print(f"Ingested doc: {ex.document_id}")

if __name__ == "__main__":
    main()
