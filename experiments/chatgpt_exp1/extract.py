# extract.py
import hashlib
import json
from llm import llm_json
from models import Extraction, GraphSchema

EXTRACT_SYSTEM = """You extract structured information from research text into a given Neo4j schema.
Return ONLY valid JSON. No markdown. No commentary.
Rules:
- Only output nodes/relationships that conform to the given schema.
- Use canonical names per normalization_rules.
- Prefer stable identifiers for Paper: DOI if present; else title; else document_id.
- Do not invent facts not supported by the text.
- IMPORTANT: For each node ref, "key" MUST be exactly the schema key for that label (Paper uses its schema key, Method uses its schema key, etc.).

"""

EXTRACT_USER_TMPL = """
Schema:
{schema_json}

Normalization rules:
{norm_json}

Document:
document_id: {document_id}
text:
<<<
{doc_text}
>>>

Return JSON:
{{
  "document_id": "...",
  "nodes": [{{"ref": {{"label":"...","key":"...","value":"..."}}, "properties": {{...}} }}],
  "relationships": [{{"type":"...","from_ref":{{...}},"to_ref":{{...}},"properties":{{...}}}}]
}}
"""

def doc_id(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]

def repair_extraction(ex_dict: dict, schema: GraphSchema) -> dict:
    label_key = {nt.label: nt.key for nt in schema.nodes}
    for n in ex_dict.get("nodes", []):
        ref = n.get("ref", {})
        lab = ref.get("label")
        if lab in label_key:
            ref["key"] = label_key[lab]
    for r in ex_dict.get("relationships", []):
        for side in ["from_ref", "to_ref"]:
            ref = r.get(side, {})
            lab = ref.get("label")
            if lab in label_key:
                ref["key"] = label_key[lab]
    return ex_dict


def extract_from_text(client, model: str, doc_text: str, schema: GraphSchema) -> Extraction:
    did = doc_id(doc_text)
    raw = llm_json(
        client=client,
        model=model,
        system=EXTRACT_SYSTEM,
        user=EXTRACT_USER_TMPL.format(
            schema_json=schema.model_dump_json(indent=2),
            norm_json=json.dumps(schema.normalization_rules, indent=2),
            document_id=did,
            doc_text=doc_text
        ),
        temperature=0.1,
    )
    raw = repair_extraction(raw, schema)
    return Extraction(**raw)
