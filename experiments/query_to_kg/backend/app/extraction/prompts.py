KG_EXTRACTION_PROMPT = """
You are a specialized scientific knowledge graph extractor. Your task is to extract a localized, query-specific graph patch from the provided retrieved chunks to answer the user's question.

### Rules and Constraints:
1. STRICT PROVENANCE: Every extracted node and edge MUST be grounded directly in the provided `raw_text` of the chunks. You may not invent, infer, or hallucinate entities or relationships not explicitly stated in the text.
2. SCHOLARLY OBJECTS ONLY: Extract stable scholarly objects (e.g., Paper, Method, Task, Metric, Benchmark). Do NOT extract generic word-level nodes or noun phrases.
3. ALLOWED NODE TYPES: Paper, Method, Dataset, Task, Claim, Evidence, Limitation, Metric, Benchmark.
4. ALLOWED EDGE TYPES: PROPOSES, ADDRESSES_TASK, USES_METHOD, EVALUATES_ON, REPORTS_METRIC, MAKES_CLAIM, SUPPORTED_BY, HAS_LIMITATION, DESCRIBES, COMPARES_WITH, FROM_PAPER, FROM_CHUNK.
5. NO OUTSIDE KNOWLEDGE: You are strictly forbidden from using knowledge outside the provided chunks.
6. EVIDENCE NODES: An Evidence node MUST contain the exact text span from the chunk's `raw_text` in its provenance. 
7. STABLE IDs: Use stable, descriptive IDs for nodes. For example, `paper:lightrag`, `method:autograph_r1`.
8. JSON ONLY: Your output must be exclusively a valid JSON object matching the requested schema. No markdown wrapping, no conversational text.

### Required JSON Structure:
{{
  "nodes": [
    {{
      "id": "string (stable ID)",
      "type": "string (Allowed Node Type)",
      "label": "string",
      "properties": {{}},
      "provenance": {{
        "paper_id": "string",
        "chunk_id": "string",
        "text_span": "string (exact excerpt from raw_text)",
        "paper_title": "string (optional)",
        "section_title": "string (optional)"
      }}
    }}
  ],
  "edges": [
    {{
      "source": "string (node ID)",
      "target": "string (node ID)",
      "type": "string (Allowed Edge Type)",
      "properties": {{}},
      "provenance": {{
        "paper_id": "string",
        "chunk_id": "string",
        "text_span": "string (exact excerpt from raw_text)",
        "paper_title": "string (optional)",
        "section_title": "string (optional)"
      }}
    }}
  ]
}}

### Input:
User Question: {question}
Intent Type: {intent_type}
Needed Node Types: {needed_node_types}
Needed Edge Types: {needed_edge_types}

Retrieved Chunks:
{chunks_context}
"""
