# schema_design.py
import json
from config import base_parser
from llm import get_client, llm_json
from models import GraphSchema

SCHEMA_SYSTEM = """You are a specialized Knowledge Graph Schema Generator.
Return ONLY a single valid JSON object matching exactly this shape:
{
  "nodes": [{"label": str, "key": str, "properties": [str]}],
  "relationships": [{"type": str, "from_label": str, "to_label": str, "properties": [str]}],
  "normalization_rules": {str: str}
}
Do not output markdown or explanations.
If input is missing/invalid, return:
{"nodes": [], "relationships": [], "normalization_rules": {}}
"""


SCHEMA_USER_TMPL = """
Analyze the following sample research text and propose a Neo4j schema.

Requirements:
- Provide node labels, relationships, unique key per label, and properties per label.
- Use labels like: Paper, Author, Method, Dataset, Task, Metric, Result, Institution, Venue (if relevant).
- Relationship types should be uppercase verbs: AUTHORED_BY, USES_METHOD, EVALUATED_ON, ADDRESSES_TASK, REPORTS_RESULT, MEASURED_BY, PUBLISHED_IN, AFFILIATED_WITH, CITES.
- Make it useful for querying: methods↔datasets↔tasks↔metrics↔results.
- Add basic normalization rules where helpful.

Sample text:
<<<
{sample_text}
>>>

Return JSON:
{{
  "nodes": [{{"label": "...", "key": "...", "properties": ["..."]}}],
  "relationships": [{{"type":"...", "from_label":"...", "to_label":"...", "properties":["..."]}}],
  "normalization_rules": {{"alias":"canonical"}}
}}
"""

def repair_schema_dict(raw: dict) -> dict:
    raw = dict(raw or {})
    raw.setdefault("nodes", [])
    raw.setdefault("relationships", [])
    raw.setdefault("normalization_rules", {})

    def fix_props(x):
        # properties must be a list[str]
        props = x.get("properties", [])
        if props is None:
            props = []
        if isinstance(props, dict):
            # if model outputs {"title": "..."} treat keys as property names
            props = list(props.keys())
        elif isinstance(props, str):
            props = [props]
        elif not isinstance(props, list):
            props = []
        # ensure list of strings only
        props = [str(p) for p in props]
        x["properties"] = props
        return x

    raw["nodes"] = [fix_props(n) for n in raw["nodes"] if isinstance(n, dict)]
    raw["relationships"] = [fix_props(r) for r in raw["relationships"] if isinstance(r, dict)]

    # normalization_rules must be dict[str,str]
    if not isinstance(raw["normalization_rules"], dict):
        raw["normalization_rules"] = {}
    raw["normalization_rules"] = {str(k): str(v) for k, v in raw["normalization_rules"].items()}

    return raw


def main():
    p = base_parser(description="Propose a Neo4j schema from sample text")
    p.add_argument("--text", required=True, help="Sample research text or @file.txt")
    p.add_argument("--out",  default="schema.json", help="Where to save the schema JSON")
    args = p.parse_args()

    text = open(args.text[1:]).read() if args.text.startswith("@") else args.text
    client = get_client(args.vllm_url)
    raw = llm_json(client, args.model, SCHEMA_SYSTEM, SCHEMA_USER_TMPL.format(sample_text=text))
    raw = repair_schema_dict(raw)
    schema = GraphSchema(**raw)

    with open(args.out, "w") as f:
        f.write(schema.model_dump_json(indent=2))
    print(f"Schema saved to {args.out}")

if __name__ == "__main__":
    main()
