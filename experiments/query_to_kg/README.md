# Query-to-KG Demo Workflow

This repository is organized into four milestones:

1. `Milestone 1`: dataset preparation
2. `Milestone 2`: contextual retrieval
3. `Milestone 3`: graph patch extraction
4. `Milestone 4`: RDF, SPARQL, and grounded answering

## Full Demo Commands

Run from the repository root:

```bash
cd /mnt/ceph/storage/data-tmp/2026/xepi3167/thesis/thesis-kumar-gupta/experiments/query_to_kg
source .venv/bin/activate

# Start the local chat and embedding servers in a separate terminal if needed.
bash vllm/serve_qwen35_litellm.sh

# Optional health check for the local services.
python vllm/test.py

# Milestone 1
python backend/scripts/generate_parsed_text.py
python backend/scripts/create_structured_papers.py
python backend/scripts/prepare_milestone_1.py

# Milestone 2
python backend/scripts/build_contextual_chunks.py
python backend/scripts/build_retrieval_index.py
python backend/scripts/test_retrieval.py

# Milestone 3
python backend/scripts/run_milestone_3_extraction.py --all-demos

# Milestone 4
python backend/scripts/run_milestone_4_answering.py --all-demos

# Final demo verification
python backend/scripts/test_sparql_pipeline.py
```

## Adding A New PDF

If you are replacing one of the existing demo papers, the workflow is close to:

1. Add the PDF under `backend/app/data/raw_pdfs/`.
2. Add a matching record to `backend/app/data/manifest.json`.
3. Regenerate Milestone 1 artifacts.
4. Rebuild Milestone 2 retrieval artifacts.
5. Re-run Milestone 3 and Milestone 4.

If you are adding a **new 4th paper**, it is **not** just “edit the manifest and run everything” yet. There are still a few hardcoded 3-paper assumptions:

- `backend/scripts/create_structured_papers.py` currently expects exactly 3 manifest records.
- `backend/scripts/run_milestone_3_extraction.py` has the three built-in demo questions and output filenames.
- `backend/scripts/run_milestone_4_answering.py` has the three built-in demo questions and patch filenames.

So for a true new-paper addition, you will usually need:

1. A new manifest entry.
2. A small code change to relax the exact-3 check in `create_structured_papers.py`.
3. Optional updates to the M3 and M4 demo mappings if you want the new paper to become a first-class built-in demo.

## Required File Shape

Each manifest entry should include:

```json
{
  "paper_id": "my_paper",
  "title": "My Paper Title",
  "year": 2026,
  "source_pdf": "backend/app/data/raw_pdfs/my_paper.pdf",
  "parsed_text": "backend/app/data/parsed_text/my_paper.txt",
  "structured_json": "backend/app/data/structured_papers/my_paper.json"
}
```

## Useful References

- [Milestone 3 contract](docs/m3_contract.md)
- [Milestone 4 contract](docs/m4.md)
