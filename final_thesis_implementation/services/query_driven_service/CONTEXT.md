# Query-Driven Retrieval Service

This service retrieves and ranks local-corpus evidence independently for each benchmark question before downstream graph construction and inference.

## Language

**Question cap**:
The maximum number of dataset questions processed by one service run.
_Avoid_: Question limit

**Search budget**:
The maximum retrieval effort available independently to each question, constrained by completed tool executions and elapsed time.
_Avoid_: Tool limit, turn limit, question limit

**Candidate document**:
A corpus document discovered during search but not necessarily inspected for relevance.
_Avoid_: Retrieved document

**Inspected document**:
A candidate document whose contents the retrieval agent has read.
_Avoid_: Search hit

**Final retrieval result**:
The validated, relevance-ranked top-k documents produced for one question.
_Avoid_: Candidates, raw retrieval

**Document reference**:
A validated locator for exactly one corpus document. File corpora use a
relative path; aggregate JSONL corpora use a relative path, byte offset, and
record ID.
_Avoid_: Corpus path
