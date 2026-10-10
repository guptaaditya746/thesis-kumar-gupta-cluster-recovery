# Thesis research: Knowledge Graphs from Scientific Documents

This repository collects the code and experiment materials for Aditya Kumar Gupta’s master thesis on building knowledge graphs from scientific documents. It includes Python services and experiments for query-driven GraphRAG, document processing, knowledge graph construction, DCI-Agent-Lite, and local LLM setup, along with notebooks and Slurm job scripts.

## Running components

The repository contains several independent services. Start with the component README for its dependencies and configuration. For the query-driven GraphRAG service:

```bash
cd final_thesis_implementation/services/query_driven_service
uv sync
uv run query-driven --config config/smoke/qa-2wikimultihopqa.toml --dry-run
```

The LLM setup tools and other services have their own `pyproject.toml`, Makefile, or README. Configure credentials through local environment variables; secret values have been blanked from published config examples. Slurm scripts are examples and may need cluster-specific paths and resource settings.

Large corpora, raw documents, model files, logs, cache directories, and runtime outputs are excluded. See `BACKUP_MANIFEST.md` for the omitted cluster files and `final_thesis_implementation/services/query_driven_service/README.md` for the service layout.
