# Milestone 3: Extraction Contract

This document defines the Milestone 3 contract from retrieved chunks to a validated graph patch. It keeps KG construction query-specific and scoped to evidence returned by Milestone 2.

## Expected Input Payload

The graph extraction process expects the following input:
1. `question` (str): The user's query.
2. `top-k RetrievedChunk results` (List[RetrievedChunk]): The ranked list of chunks retrieved by the `RetrievalService` in Milestone 2.

The retrieved chunks provide the following fields:
- `chunk_id`
- `paper_id`
- `paper_title`
- `section_id`
- `section_title`
- `raw_text`
- `contextual_summary`
- `page_start`
- `page_end`
- `score`
- `rank`
- `retrieval_method`

## Graph Patch Output

The output is a validated query-specific graph patch JSON with nodes and edges. It is NOT a full corpus KG, RDF, or SPARQL. The graph patch is constructed *after* the question and built *only* from the retrieved chunks.

Every node and edge must contain strict provenance back to the source text. 

### Provenance Requirements
Every graph node and edge must trace back to real evidence from the chunks:
- `paper_id`
- `paper_title`
- `section_title`
- `chunk_id`
- `text_span`

`raw_text` is the ONLY source evidence. `contextual_summary`, `retrieval_tags`, and `index_text` are retrieval helpers only. Every `text_span` in the graph patch must come directly from `raw_text`.

## MVP Graph Vocabulary

Stable scholarly objects are modeled as nodes. Word-level noise and generic noun phrases are excluded.

### Allowed Node Types
- `Paper`
- `Method`
- `Dataset`
- `Task`
- `Claim`
- `Evidence`
- `Limitation`
- `Metric`
- `Benchmark`

### Allowed Edge Types
- `PROPOSES`
- `ADDRESSES_TASK`
- `USES_METHOD`
- `EVALUATES_ON`
- `REPORTS_METRIC`
- `MAKES_CLAIM`
- `SUPPORTED_BY`
- `HAS_LIMITATION`
- `DESCRIBES`
- `COMPARES_WITH`
- `FROM_PAPER`
- `FROM_CHUNK`

## Sample Output Artifacts needed by M4
The output expected for M4 is a JSON payload representing the query-specific graph patch.
For example, a request about "Which paper proposes a reinforcement-learning approach for knowledge graph construction?" should yield an extraction containing the relevant `Paper` and `Method` nodes connected by a `PROPOSES` edge, with `Evidence` extracted from the chunks, strictly retaining source provenance (paper, section, chunk ID, exact text span).

Sample graph patch JSON:
```json
{
  "nodes": [
    {
      "id": "node_1",
      "type": "Paper",
      "label": "AutoGraph-R1",
      "provenance": { "paper_id": "autograph_r1", "paper_title": "...", "section_title": "...", "chunk_id": "...", "text_span": "..." }
    }
  ],
  "edges": [
    {
      "source": "node_1",
      "target": "node_2",
      "type": "PROPOSES",
      "provenance": { "paper_id": "autograph_r1", "paper_title": "...", "section_title": "...", "chunk_id": "...", "text_span": "..." }
    }
  ]
}
```
