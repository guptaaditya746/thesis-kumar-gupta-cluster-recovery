Milestone 1 dataset structure
Generated files
Raw PDF location
Parsed text location
Structured paper JSON location
Base chunks JSONL location
How to regenerate the dataset
What is not included yet

python backend/scripts/prepare_milestone_1.py

some manual checks
backend/app/data/chunks/base_chunks.jsonl

Check each sample has:

readable text
correct paper title
correct section title
stable chunk ID
valid previous/next chunk link where applicable

Milestone 2 retrieval workflow

Commands

python backend/scripts/build_contextual_chunks.py
python backend/scripts/build_retrieval_index.py
python backend/scripts/test_retrieval.py

Artifacts

backend/app/data/chunks/contextualized_chunks.jsonl
backend/app/data/indexes/llamaindex_vector/
backend/app/data/indexes/bm25_index.pkl
backend/app/data/eval/retrieval_gold.json

Evidence rule

raw_text is the only source evidence.
contextual_summary, retrieval_tags, and index_text are retrieval helpers only.
retrieval output in Milestone 2 does not create KG nodes, RDF triples, SPARQL, or final answers.

Great. Let’s start **M2-I12: Document Contextual Chunking And Retrieval Workflow**. This one is documentation only, no new retrieval behavior, no KG extraction, no RDF, no SPARQL, no FastAPI endpoint. Just turning your Milestone 2 work into a reproducible trail of breadcrumbs.

## M2-I12 goal

You need to document:

```text
how to reproduce Milestone 2 outputs
what each artifact means
how contextual chunks are built
how vector, BM25, and hybrid retrieval work
what evaluation command proves retrieval is working
```

And keep the evidence rule visible:

```text
raw_text is the only source evidence.
contextual_summary, retrieval_tags, and index_text are retrieval helpers only.
```

## First documentation step

Open:

```text
docs/project-log.md
```

Add this section near your Milestone 2 notes.

````md
## M2-I12: Contextual Chunking And Retrieval Workflow

Milestone 2 builds the retrieval layer for the `query_to_kg` experiment.

The goal of this milestone is to prepare paper chunks for retrieval and expose a stable retrieval interface for later milestones. This milestone does not create KG nodes, RDF triples, SPARQL queries, or final answers.

### Evidence Rule

`raw_text` is the only source evidence.

The following fields are retrieval helpers only:

- `contextual_summary`
- `retrieval_tags`
- `index_text`

These helper fields may improve retrieval quality, but they must not be treated as source evidence. Later KG extraction must use `raw_text` as the evidence source.

### Reproduction Commands

Run all commands from the experiment root:

```bash
cd experiments/query_to_kg
```
````

Build contextual chunks:

```bash
python backend/scripts/build_contextual_chunks.py
```

Build retrieval indexes:

```bash
python backend/scripts/build_retrieval_index.py
```

Run retrieval evaluation:

```bash
python3 -m backend.scripts.test_retrieval
```

### Artifact Summary

#### `backend/app/data/chunks/base_chunks.jsonl`

Produced by Milestone 1.

Purpose:

- stores the original paper chunks
- acts as the input to contextual chunking
- preserves chunk-level source text before retrieval enrichment

#### `backend/app/data/chunks/contextualized_chunks.jsonl`

Produced by Milestone 2 contextualization.

Purpose:

- stores retrieval-ready chunk records
- adds contextual summaries and retrieval tags
- builds `index_text` for retrieval indexing
- preserves `raw_text` as the evidence-bearing field

Each contextualized chunk contains fields such as:

```text
chunk_id
paper_id
paper_title
section_id
section_title
chunk_index
raw_text
contextual_summary
retrieval_tags
index_text
page_start
page_end
previous_chunk_id
next_chunk_id
source_type
```

The `index_text` field combines paper title, section title, contextual summary, retrieval tags, and raw source chunk text for retrieval.

#### Vector Index

Path:

```text
backend/app/data/indexes/llamaindex_vector/
```

Produced by:

```bash
python backend/scripts/build_retrieval_index.py
```

Purpose:

- supports dense semantic retrieval
- indexes each contextual chunk using `index_text`
- helps retrieve conceptually relevant chunks even when wording differs

#### BM25 Index

Path:

```text
backend/app/data/indexes/bm25_index.pkl
```

Produced by:

```bash
python backend/scripts/build_retrieval_index.py
```

Purpose:

- supports sparse lexical retrieval
- helps retrieve exact names and technical terms
- preserves terms such as `LightRAG`, `AutoGraph-R1`, `Text2Cypher`, `SPARQL`, `RDF`, and `GRPO`

#### Retrieval Gold File

Path:

```text
backend/app/data/eval/retrieval_gold.json
```

Produced by Milestone 2 evaluation setup.

Purpose:

- stores small demo retrieval questions
- defines expected papers
- supports Hit@1, Hit@3, Hit@5, and expected term coverage checks

### Retrieval Flow

Milestone 2 retrieval follows this flow:

```text
contextualized_chunks.jsonl
    ↓
vector index over index_text
    ↓
BM25 index over retrieval fields
    ↓
hybrid retrieval with reciprocal rank fusion
    ↓
top-k RetrievedChunk results
```

The hybrid retriever combines vector and BM25 results using reciprocal rank fusion. The final score is a fusion score, not a confidence score.

### Retrieval Service

Later milestones should call retrieval through `RetrievalService` instead of calling vector, BM25, or hybrid retrievers directly.

Example:

```python
from backend.app.retrieval.retrieval_service import RetrievalService

service = RetrievalService()
results = service.retrieve("What is AutoGraph-R1?", top_k=5)
```

The service hides:

- vector retrieval internals
- BM25 retrieval internals
- reciprocal-rank fusion internals
- retrieval defaults

### Retrieval Evaluation Result

The retrieval evaluation was run with:

```bash
python3 -m backend.scripts.test_retrieval
```

Observed result:

```text
Hit@1: 3/3
Hit@3: 3/3
Hit@5: 3/3
Expected term coverage: 3/3
Target Hit@3 = 3/3: PASSED
```

Demo questions covered the expected papers:

```text
LightRAG
AutoGraph-R1
Mind the Query
```

### Current Limitations

Retrieval is working for the Milestone 2 demo set, but the evaluation is intentionally small.

Known limitations:

- RRF scores are not confidence scores.
- Retrieval has only been evaluated on three demo questions.
- Reference chunks may rank highly when they contain exact matching terms.
- Dense retrieval may blur exact scientific names.
- BM25 is lexical and does not capture deeper semantic similarity.
- RAGAS-style evaluation should wait until answer generation exists.

### Milestone 2 Status

M2-I10 is complete.

M2-I11 is complete.

M2-I12 is complete once this workflow documentation is committed.

````

## Then run this check

```bash
grep -n "M2-I12\|Evidence Rule\|Reproduction Commands\|Retrieval Flow\|Hit@3" docs/project-log.md
````

Expected: you should see matching lines for the new section.

After that, your Milestone 2 trio is done:

```text
M2-I10: retrieval service and combined index build
M2-I11: retrieval demo questions and evaluation report
M2-I12: contextual chunking and retrieval workflow documentation
```
