

# 1️⃣ Core GraphRAG Framework (MOST IMPORTANT)

These are the actual packages implementing the GraphRAG pipeline.

Relevant for: **your thesis core pipeline**

* `graphrag`
* `graphrag-common`
* `graphrag-input`
* `graphrag-chunking`
* `graphrag-llm`
* `graphrag-vectors`
* `graphrag-storage`
* `graphrag-cache`

What they do:

| Package           | Role                       |
| ----------------- | -------------------------- |
| graphrag-input    | document ingestion         |
| graphrag-chunking | splitting documents        |
| graphrag-llm      | entity/relation extraction |
| graphrag-vectors  | embeddings                 |
| graphrag-storage  | storing graph data         |
| graphrag-cache    | caching LLM responses      |

💡 These packages implement the **GraphRAG pipeline described in the Microsoft GraphRAG paper**.

---

# 2️⃣ LLM Interface Layer

Relevant for: **entity and relation extraction**

### LiteLLM

This is what you already noticed.

Purpose:

* unified interface for many LLM APIs
* supports OpenAI, Azure, Ollama, HuggingFace, etc.

Example usage:

```python
import litellm

response = litellm.completion(
    model="gpt-4o-mini",
    messages=[{"role":"user","content":"Extract entities"}]
)
```

For your thesis:

LLM will do

```
Paper text
↓
Entity extraction
↓
Triples
```

So **litellm is critical**.

---

# 3️⃣ Graph Structure & Graph Algorithms

Relevant for: **knowledge graph structure**

### NetworkX

Used for:

* graph creation
* graph analysis
* graph traversal

Example:

```python
import networkx as nx

G = nx.Graph()
G.add_edge("Paper", "Author", relation="written_by")
```

This is important if you:

* analyze co-author networks
* compute graph metrics

---

# 4️⃣ Vector Search / Embedding Storage

Relevant for: **semantic retrieval**

### LanceDB

Purpose:

* vector database
* embedding search
* semantic retrieval

Used for:

```
text
↓
embedding
↓
vector search
```

GraphRAG uses vectors to retrieve **relevant text before graph reasoning**.

---

# 5️⃣ NLP Processing

Relevant for: **text processing before KG creation**

### spaCy

Used for:

* Named Entity Recognition
* tokenization
* linguistic processing

Example:

```python
import spacy
nlp = spacy.load("en_core_web_sm")
doc = nlp("John works at Microsoft.")
```

Entities:

```
John -> PERSON
Microsoft -> ORG
```

---

# 6️⃣ Document Processing

Relevant for: **reading papers or PDFs**

Key libraries:

| Library        | Purpose                 |
| -------------- | ----------------------- |
| pdfplumber     | extract text from PDFs  |
| pdfminer-six   | PDF parsing             |
| beautifulsoup4 | parse HTML              |
| markdownify    | convert HTML → markdown |

Useful if you extract text from:

* PDFs
* HTML
* websites

---

# 7️⃣ Data Processing

Relevant for: **data cleaning**

Important ones:

| Library | Purpose              |
| ------- | -------------------- |
| pandas  | data manipulation    |
| numpy   | numerical processing |
| pyarrow | fast column storage  |

Example:

```python
import pandas as pd
df = pd.read_json("papers.json")
```

---

# 8️⃣ Azure Cloud (Probably Not Needed)

These appear because GraphRAG supports Azure.

Examples:

* `azure-identity`
* `azure-cosmos`
* `azure-search-documents`
* `azure-storage-blob`

You **probably won't need them** unless deploying on Azure.

---

# ⭐ The 8 MOST RELEVANT Packages for Your Thesis

Focus on understanding these:

1️⃣ `graphrag`
2️⃣ `graphrag-llm`
3️⃣ `litellm`
4️⃣ `networkx`
5️⃣ `lancedb`
6️⃣ `spacy`
7️⃣ `pandas`
8️⃣ `tiktoken`

Everything else is mostly **supporting infrastructure**.

---

# 🔑 How These Fit Into Your Thesis Pipeline

Your pipeline likely becomes:

```
IR Anthology (BibTex / JSON)
        │
        ▼
Document Parsing
(pdfplumber / bs4)
        │
        ▼
Chunking
(graphrag-chunking)
        │
        ▼
Entity Extraction
(litellm / graphrag-llm)
        │
        ▼
Triples
(Paper → Author)
        │
        ▼
Graph Construction
(networkx)
        │
        ▼
Vector Search
(lancedb)
```

---
