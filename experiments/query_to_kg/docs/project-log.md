Epic:
  M1: Paper Data Foundation and Provenance Layer

Status:
  In progress
  Completed through: M1-WI-04

Work Items:
  [x] M1-WI-01: Create folder structure
      Notes:
      - Folder structure for Milestone 1 was created.

  [x] M1-WI-02: Add raw PDFs
      Notes:
      - Raw PDFs were added.
      - Nothing unusual found so far.

  [x] M1-WI-03: Create manifest
      Notes:
      - manifest.json was created.
      - Manifest was later modified to match the current paper paths and metadata.

  [x] M1-WI-04: Define Pydantic schemas
      Notes:
      - Created Pydantic schemas in backend/app/ingestion/schemas.py.
      - Added models for PaperMetadata, Section, PaperDocument, and BaseChunk.
      - Added docstrings to explain the purpose of each schema.
      - Used optional fields for metadata or provenance values that may not always be available.
      - Used default empty lists for authors, sections, and references.
 
 [x] M1-WI-05: Implement paper loader
    Notes:
    - Created backend/app/ingestion/paper_loader.py.
    - Loader reads backend/app/data/manifest.json.
    - Loader returns all 3 paper records.
    - Loader validates expected PDF paths.
    - Loader validates parsed text paths when present.
    - Missing files produce clear error messages.

[x] M1-WI-06: Generate/load parsed text
    Notes:
    - Generated parsed text files for LightRAG, AutoGraph-R1, and Mind the Query.
    - Used Docling as the working parser because it produced good text output.
    - Added parser interface in backend/app/ingestion/parsed_text_generator.py.
    - Added script entry point in backend/scripts/generate_parsed_text.py.
    - Confirmed parsed text files exist under backend/app/data/parsed_text/.
    - Manual inspection showed meaningful extracted paper content.
    - Future improvements may compare parsing engines, add parallel parsing, or preserve richer academic structure.

    What was done:
- Generated parsed text files for all 3 papers.
- Confirmed that Docling works and produces good-quality text output.
- Stored parsed text files under backend/app/data/parsed_text/.
- Added a parser interface so the parsing engine can be changed later without changing the rest of the ingestion pipeline.
- Kept the implementation milestone-focused: parsed text generation only, no section parsing, chunking, KG extraction, or retrieval logic.

Acceptance criteria:
- lightrag.txt exists.
- autograph_r1.txt exists.
- mind_the_query.txt exists.
- All files contain meaningful extracted paper content.
- PDF parsing no longer blocks the milestone.

Future work notes:
- The parsing interface can later be extended for parallel processing, parser benchmarking, caching, or parser-specific metadata.
- Academic structure extraction can be improved in M1-WI-07 when implementing the section parser.
- Future experiments can compare Docling, LiteParse, and PyMuPDF based on heading quality, abstract/reference detection, table handling, citation noise, reading order, and section boundary quality.
- LLMs and embeddings should not be used in this work item yet; they may be useful later for structure cleanup, semantic chunking, or validation.



  [ ] M1-WI-07: Implement section parser
  [ ] M1-WI-08: Create structured paper JSON
  [ ] M1-WI-09: Implement base chunker
  [ ] M1-WI-10: Create base_chunks.jsonl
  [ ] M1-WI-11: Implement validation script
  [ ] M1-WI-12: Create prepare_milestone_1.py
  [ ] M1-WI-13: Add README dataset notes
  [ ] M1-WI-14: Manually inspect sample chunks
  [ ] M1-WI-15: Final milestone completion check

Decisions:
  - Keep Milestone 1 focused only on the data foundation.
  - Do not build KG extraction, SPARQL, retrieval, or UI in this milestone.
  - Define schemas before writing loaders, parsers, or chunkers.
  - Use stable IDs such as paper_id, section_id, and chunk_id for provenance.
  - Keep page_start, page_end, char_start, and char_end optional for now because parsed text may not always contain reliable location data.
  - Keep references flexible as dictionaries because reference metadata may vary across papers.

Assumptions:
  - The project currently uses three papers: LightRAG, AutoGraph-R1, and Mind the Query.
  - Parsed text may come from existing text files, LlamaParse output, or a PyMuPDF fallback.
  - The schema layer should only define valid data shapes. It should not parse PDFs, split sections, or create chunks.
  - The password hashing decision belongs to a different backend/auth task and is not part of Milestone 1 unless authentication is added later.

Epic:
  M2: Retrieval Layer and Contextualized Chunks

Status:
  Completed

Work Items:
  [x] M2-I10: RetrievalService works
  [x] M2-I11: retrieval eval passes
  [x] M2-I12: workflow documented

Epic:
  M3: Query-to-Graph Extraction

Status:
  In progress

Work Items:
  [x] M3-01: Document Extraction Contract
      Notes:
      - Documented expected input payload containing question and retrieved chunks.
      - Documented graph patch output with nodes, edges, and provenance.
      - Listed allowed MVP node types (Paper, Method, etc.) and edge types (PROPOSES, etc.).
      - Recorded the rule that stable scholarly objects are nodes and word-level noise is excluded.
      - Identified sample output artifacts needed by Milestone 4.
      - Contract is available in docs/m3_contract.md.

  [x] M3-02: Implement Graph Patch Pydantic Schemas
      Notes:
      - Renamed Node/Edge to KGNode/KGEdge to avoid name collisions.
      - Defined NodeType and EdgeType based on milestone vocabulary.
      - Added strict Provenance model requiring paper_id, chunk_id, and text_span.
      - Permitted flexible schema properties (via `properties` dict) while enforcing types.
      - Created schema examples and validation tests mapping to demo questions in `test_graph_patch_schema.py`.

  [x] M3-03: Implement Query Understanding
      Notes:
      - Created `query_understanding.py` with rule-based categorization.
      - Mapped demo questions to intents (method_proposal, claim_evidence, benchmark_evaluation).
      - Added rules for limitation and comparison queries.
      - Exported `QueryIntent` schema defining `needed_node_types` and `needed_edge_types`.
      - Added fallback logic to prevent unhandled exceptions on unknown queries.
      - Confirmed logic using `test_query_understanding.py`.

  [x] M3-04: Implement KG Extraction Service
      Notes:
      - Created `prompts.py` enforcing JSON-only output, allowed scholarly types, and strict textual provenance.
      - Developed `KGExtractor` class in `kg_extractor.py` to interface with the LLM via `litellm`.
      - Extractor merges the user question, categorized `QueryIntent`, and the `RetrievedChunk` strings.
      - Integrated safeguards to clean malformed JSON output (e.g., markdown wrappers) and surface validation errors.
      - Wrote tests in `test_kg_extractor.py` validating string construction and mock-LLM schema extraction.


  [x] M3-I08: Create Milestone 3 extraction runner
      Notes:
      - Added `backend/scripts/run_milestone_3_extraction.py` as the reproducible Milestone 3 entry point.
      - Runner loads Milestone 2 contextualized chunks indirectly through `RetrievalService` and validates that retrieval indexes exist before execution.
      - Pipeline stages are explicit and ordered as retrieval, query understanding, extraction, validation, entity resolution, and graph-patch cleaning.
      - Default execution writes the cleaned patch for the selected demo question under `backend/app/data/graph_patches/`.
      - `--all-demos` runs the three milestone demo questions and writes the stable output filenames expected by Milestone 4.
      - Failures are surfaced as stage-specific errors so it is clear whether retrieval, extraction, validation, entity resolution, or cleaning failed.

      Commands:
      - `python backend/scripts/run_milestone_3_extraction.py`
      - `python backend/scripts/run_milestone_3_extraction.py --demo lightrag`
      - `python backend/scripts/run_milestone_3_extraction.py --all-demos`

      Expected output summary:
      - Question
      - Contextualized chunk count
      - Retrieved chunk count
      - Top paper
      - Query type
      - Node count
      - Edge count
      - Validation status
      - Save path

  [ ] M3-I09: Save sample graph patches for demo questions
      Notes:
      - Target artifact paths are:
        `backend/app/data/graph_patches/sample_graph_patch_autograph.json`
        `backend/app/data/graph_patches/sample_graph_patch_lightrag.json`
        `backend/app/data/graph_patches/sample_graph_patch_mind_the_query.json`
      - These files are generated by `python backend/scripts/run_milestone_3_extraction.py --all-demos` once the local extraction backend is available.
      - The runner preserves source chunk provenance in node and edge provenance fields for Milestone 4 evidence work.
      - Artifact generation remains environment-dependent because `KGExtractor` currently calls the local OpenAI-compatible endpoint at `http://127.0.0.1:8000/v1`.

  [x] M3-I11: Document dynamic KG construction workflow
      Notes:
      - Milestone 3 constructs a query-specific graph only after Milestone 2 retrieval returns relevant chunks; it does not build a full corpus KG.
      - Allowed scholarly node types and edge types are defined in `docs/m3_contract.md` and enforced by schema plus validation checks.
      - Entity resolution is alias-based and intentionally lightweight; canonical rewrites currently cover milestone-specific aliases such as `LightRAG`, `AutoGraph-R1`, `Mind the Query`, and `Knowledge Graph Construction`.
      - Validation checks enforce node/edge schema correctness, endpoint existence, strict provenance fields, and direct substring provenance against retrieved chunk text when available.
      - Cleaning removes low-quality nodes, merges duplicate canonical entities and edges, and prunes unsupported evidence nodes before final validation.
      - RDF generation and SPARQL querying remain out of scope for Milestone 3; the cleaned graph patch JSON files are the handoff artifacts for Milestone 4.
