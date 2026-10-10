# Backup manifest: thesis-kumar-gupta

Fresh sanitized source snapshot; source history is omitted because credential-bearing history is retained only in the original local checkout. The source worktree and all excluded files were left in place. Tracked source edits are included; untracked logs, `.orig` backups, and agent-session files are excluded.

## Excluded groups
- `credentials and environments/` — 9 files omitted (0 bytes of tracked files); credential-bearing config or binary dump, generated data, cache, environment, log, or output directory.
- `experiments/` — 3233 files omitted (7407690 bytes of tracked files); binary file, credential-bearing config or binary dump, generated data, cache, environment, log, or output directory, generated, compiled, backup, log, data, or binary artifact.
- `final_thesis_implementation/` — 121 files omitted (0 bytes of tracked files); generated data, cache, environment, log, or output directory, generated, compiled, backup, log, data, or binary artifact.
- `reports/` — 1 files omitted (0 bytes of tracked files); generated data, cache, environment, log, or output directory.

## Large tracked files omitted

## Credentials scrubbed or excluded

- `experiments/knowledge-graphs-and-llms-in-action/config.ini` excluded; it contains Neo4j connection fields. The same project is separately staged as a sanitized source snapshot.
- `.env` files are excluded; `.env.example` and `.env.template` files are kept only with credential values blanked.
- Credential fields in YAML, TOML, INI, and JSON config examples were blanked. Check each component’s docs for required environment variable names. Rotate any value if it was valid or exposed elsewhere.

## Configuration files scrubbed
- `experiments/docling/tutorial/scratch/paper.json`
- `experiments/edc/environment.yml`
- `experiments/microsoft_graphrag/settings.yaml`
- `experiments/query_to_kg/vllm/litellm_config.yaml`
- `final_thesis_implementation/llm_setup/config/litellm.yaml`
- `final_thesis_implementation/llm_setup/config/vllm_models.toml`
- `final_thesis_implementation/services/dci/config/answer_qa/2wikimultihopqa.toml`
- `final_thesis_implementation/services/dci/config/answer_qa/bamboogle.toml`
- `final_thesis_implementation/services/dci/config/answer_qa/browsecomp_plus.toml`
- `final_thesis_implementation/services/dci/config/answer_qa/hotpotqa.toml`
- `final_thesis_implementation/services/dci/config/answer_qa/musique.toml`
- `final_thesis_implementation/services/dci/config/answer_qa/nq.toml`
- `final_thesis_implementation/services/dci/config/answer_qa/triviaqa.toml`
- `final_thesis_implementation/services/dci/config/single.toml`
- `final_thesis_implementation/services/query_driven_service/config/bright/biology.toml`
- `final_thesis_implementation/services/query_driven_service/config/bright/earth_science.toml`
- `final_thesis_implementation/services/query_driven_service/config/bright/economics.toml`
- `final_thesis_implementation/services/query_driven_service/config/bright/robotics.toml`
- `final_thesis_implementation/services/query_driven_service/config/examples/bright.toml`
- `final_thesis_implementation/services/query_driven_service/config/qa/2wikimultihopqa.toml`
- `final_thesis_implementation/services/query_driven_service/config/qa/bamboogle.toml`
- `final_thesis_implementation/services/query_driven_service/config/qa/hotpotqa.toml`
- `final_thesis_implementation/services/query_driven_service/config/qa/musique.toml`
- `final_thesis_implementation/services/query_driven_service/config/qa/nq.toml`
- `final_thesis_implementation/services/query_driven_service/config/qa/triviaqa.toml`
- `final_thesis_implementation/services/query_driven_service/config/reproduction/mmqa.toml`
- `final_thesis_implementation/services/query_driven_service/config/reproduction/webqa.toml`
- `final_thesis_implementation/services/query_driven_service/config/smoke/bright-biology.toml`
- `final_thesis_implementation/services/query_driven_service/config/smoke/generic-jsonl-qa.toml`
- `final_thesis_implementation/services/query_driven_service/config/smoke/qa-2wikimultihopqa.toml`

## Notable local-only artifacts and datasets

- `final_thesis_implementation/services/pi_runtime/pi-mono` — 631,694,930 bytes (about 632 MB).
- `experiments/chatgpt_exp1/core` — 20,967,424 bytes (core dump).
- `experiments/knowledge-graphs-and-llms-in-action/` — duplicate book-project tree; published separately as its own sanitized repository.
- `experiments/query_to_kg/backend/app/data/raw_pdfs/` and `experiments/docling/data/` — source PDFs and benchmark data.
- `final_thesis_implementation/llm_setup/test_results/`, `final_thesis_implementation/services/pi_runtime/.pi/agent/sessions/`, and experiment logs — generated results and agent sessions.
- Notebook code is retained, but execution outputs were cleared from the public snapshots.

The local LiteLLM configuration included populated `api_key`, `master_key`, and `default_api_key` fields; config copies blank those fields. The bundled VLLM smoke scripts had token-shaped local test defaults; these now read `VLLM_API_KEY` from the environment. Rotate any such value if it was valid or used outside local testing.
