"""
chunking_inspector.py

Purpose
-------
Convert a source document with Docling, chunk it with HybridChunker, and inspect
the resulting chunks in a way that is easy to understand, compare, and modify.

Why this script is useful for GraphRAG
--------------------------------------
In GraphRAG pipelines, chunk quality matters because chunks often become:
1. the units used for embedding,
2. the basis for entity/relation extraction,
3. the source nodes or evidence in the graph,
4. the retrieval context returned to the LLM.

This script helps you study:
- how a document is segmented,
- how many tokens each chunk contains,
- what extra context is added by `chunker.contextualize(...)`,
- whether chunk sizes are suitable for downstream embedding and retrieval.

You can adapt this script for:
- chunking experiments,
- ablation studies,
- embedding pipeline preparation,
- chunk statistics for thesis figures/tables.

Requirements
------------
pip install docling transformers sentence-transformers

Optional for OpenAI tokenizer path:
pip install tiktoken
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Any
import json
import statistics


# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------

@dataclass
class ChunkingConfig:
    """
    Central configuration for the experiment.

    Adjust these values instead of editing logic throughout the script.
    """
    # Input document path
    doc_source: str = "../tutorial/scratch/paper.md"

    # Tokenizer settings
    tokenizer_backend: str = "huggingface"  # "huggingface" or "openai"
    embed_model_id: str = "sentence-transformers/all-MiniLM-L6-v2"
    max_tokens: int = 64

    # Chunker settings
    merge_peers: bool = True

    # Output / reporting settings
    preview_chars: int = 300
    print_contextualized_text: bool = True
    print_raw_chunk_text: bool = True
    save_json: bool = False
    json_output_path: str = "chunk_report.json"


# -----------------------------------------------------------------------------
# Imports that depend on installed libraries
# -----------------------------------------------------------------------------

from docling.document_converter import DocumentConverter
from docling.chunking import HybridChunker


# -----------------------------------------------------------------------------
# Tokenizer factory
# -----------------------------------------------------------------------------

def build_tokenizer(config: ChunkingConfig) -> Any:
    """
    Build a tokenizer object compatible with Docling's HybridChunker.

    Supported backends:
    - huggingface
    - openai

    Returns
    -------
    tokenizer : object
        A tokenizer instance with a `count_tokens(text)` method.
    """
    backend = config.tokenizer_backend.lower().strip()

    if backend == "huggingface":
        from docling_core.transforms.chunker.tokenizer.huggingface import (
            HuggingFaceTokenizer,
        )
        from transformers import AutoTokenizer

        hf_tokenizer = AutoTokenizer.from_pretrained(config.embed_model_id)

        tokenizer = HuggingFaceTokenizer(
            tokenizer=hf_tokenizer,
            max_tokens=config.max_tokens,
        )
        return tokenizer

    if backend == "openai":
        # Optional path if you want to align chunking with an OpenAI model tokenizer.
        import tiktoken
        from docling_core.transforms.chunker.tokenizer.openai import OpenAITokenizer

        # Replace "gpt-4o" with another OpenAI model if needed.
        encoding = tiktoken.encoding_for_model("gpt-4o")

        tokenizer = OpenAITokenizer(
            tokenizer=encoding,
            # For OpenAI tokenizers, this is typically the model context size.
            max_tokens=128 * 1024,
        )
        return tokenizer

    raise ValueError(
        f"Unsupported tokenizer_backend={config.tokenizer_backend!r}. "
        "Use 'huggingface' or 'openai'."
    )


# -----------------------------------------------------------------------------
# Document loading
# -----------------------------------------------------------------------------

def load_document(doc_source: str):
    """
    Convert the source document into a Docling document.

    Parameters
    ----------
    doc_source : str
        Path to the input document. Can be markdown, PDF, etc. depending on
        what Docling supports in your environment.

    Returns
    -------
    doc : Docling document
        Parsed document object.
    """
    source_path = Path(doc_source)
    if not source_path.exists():
        raise FileNotFoundError(f"Document not found: {source_path.resolve()}")

    converter = DocumentConverter()
    result = converter.convert(source=str(source_path))
    return result.document


# -----------------------------------------------------------------------------
# Chunking
# -----------------------------------------------------------------------------

def build_chunker(tokenizer: Any, config: ChunkingConfig) -> HybridChunker:
    """
    Create a HybridChunker configured for the current experiment.
    """
    return HybridChunker(
        tokenizer=tokenizer,
        merge_peers=config.merge_peers,
    )


def generate_chunks(doc: Any, chunker: HybridChunker) -> List[Any]:
    """
    Run chunking and materialize the iterator into a list.

    Materializing is useful for:
    - repeated analysis,
    - statistics,
    - saving reports,
    - debugging.
    """
    return list(chunker.chunk(dl_doc=doc))


# -----------------------------------------------------------------------------
# Chunk inspection helpers
# -----------------------------------------------------------------------------

def safe_preview(text: str, max_chars: int) -> str:
    """
    Shorten text for terminal display.
    """
    text = text.replace("\n", "\\n")
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + " ..."


def inspect_chunks(
    chunks: List[Any],
    chunker: HybridChunker,
    tokenizer: Any,
    config: ChunkingConfig,
) -> List[dict]:
    """
    Inspect each chunk and return a structured report.

    Each report entry includes:
    - chunk index
    - raw chunk text
    - raw token count
    - contextualized text
    - contextualized token count

    This is helpful for thesis analysis because contextualization may improve
    retrieval performance, but it also increases token count.
    """
    report = []

    for i, chunk in enumerate(chunks):
        raw_text = chunk.text
        raw_tokens = tokenizer.count_tokens(raw_text)

        contextualized_text = chunker.contextualize(chunk=chunk)
        contextualized_tokens = tokenizer.count_tokens(contextualized_text)

        item = {
            "chunk_index": i,
            "raw_text": raw_text,
            "raw_tokens": raw_tokens,
            "contextualized_text": contextualized_text,
            "contextualized_tokens": contextualized_tokens,
            "token_overhead": contextualized_tokens - raw_tokens,
        }
        report.append(item)

        print(f"\n=== CHUNK {i} ===")

        if config.print_raw_chunk_text:
            print(f"raw_text ({raw_tokens} tokens):")
            print(repr(safe_preview(raw_text, config.preview_chars)))

        if config.print_contextualized_text:
            print(f"contextualized_text ({contextualized_tokens} tokens):")
            print(repr(safe_preview(contextualized_text, config.preview_chars)))

        print(f"token_overhead: {contextualized_tokens - raw_tokens}")

    return report


# -----------------------------------------------------------------------------
# Statistics
# -----------------------------------------------------------------------------

def summarize_report(report: List[dict]) -> None:
    """
    Print summary statistics across all chunks.

    These numbers are useful for:
    - comparing chunking strategies,
    - deciding an embedding budget,
    - understanding how much contextualization expands the text.
    """
    if not report:
        print("\nNo chunks were generated.")
        return

    raw_counts = [item["raw_tokens"] for item in report]
    contextualized_counts = [item["contextualized_tokens"] for item in report]
    overheads = [item["token_overhead"] for item in report]

    print("\n" + "=" * 72)
    print("SUMMARY")
    print("=" * 72)
    print(f"Number of chunks: {len(report)}")
    print(
        f"Raw tokens      -> min={min(raw_counts)}, max={max(raw_counts)}, "
        f"mean={statistics.mean(raw_counts):.2f}, median={statistics.median(raw_counts)}"
    )
    print(
        f"Context tokens  -> min={min(contextualized_counts)}, max={max(contextualized_counts)}, "
        f"mean={statistics.mean(contextualized_counts):.2f}, median={statistics.median(contextualized_counts)}"
    )
    print(
        f"Overhead tokens -> min={min(overheads)}, max={max(overheads)}, "
        f"mean={statistics.mean(overheads):.2f}, median={statistics.median(overheads)}"
    )

    # A few thesis-relevant observations in plain language
    print("\nInterpretation notes:")
    print("- Larger chunks may preserve more semantic coherence but can reduce retrieval precision.")
    print("- Smaller chunks may improve fine-grained retrieval but risk fragmenting context.")
    print("- Contextualization adds useful metadata/context, but increases embedding cost.")
    print("- In GraphRAG, chunk boundaries can affect entity and relation extraction quality.")


# -----------------------------------------------------------------------------
# Persistence
# -----------------------------------------------------------------------------

def save_report_json(report: List[dict], output_path: str) -> None:
    """
    Save the chunk report to JSON for later analysis.

    This is useful for:
    - plotting token distributions,
    - comparing multiple chunking runs,
    - storing results for a thesis appendix or reproducibility package.
    """
    path = Path(output_path)
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nSaved report to: {path.resolve()}")


# -----------------------------------------------------------------------------
# Main pipeline
# -----------------------------------------------------------------------------

def main() -> None:
    """
    End-to-end experiment pipeline.
    """
    config = ChunkingConfig()

    print("=" * 72)
    print("DOC CHUNKING INSPECTOR")
    print("=" * 72)
    print(f"Document source      : {config.doc_source}")
    print(f"Tokenizer backend    : {config.tokenizer_backend}")
    print(f"Embedding model      : {config.embed_model_id}")
    print(f"Max tokens           : {config.max_tokens}")
    print(f"merge_peers          : {config.merge_peers}")

    # 1. Load document
    doc = load_document(config.doc_source)

    # 2. Build tokenizer
    tokenizer = build_tokenizer(config)

    # 3. Build chunker
    chunker = build_chunker(tokenizer, config)

    # 4. Generate chunks
    chunks = generate_chunks(doc, chunker)
    print(f"\nGenerated {len(chunks)} chunks.")

    # 5. Inspect chunks
    report = inspect_chunks(
        chunks=chunks,
        chunker=chunker,
        tokenizer=tokenizer,
        config=config,
    )

    # 6. Print summary statistics
    summarize_report(report)

    # 7. Optionally save results
    if config.save_json:
        save_report_json(report, config.json_output_path)


if __name__ == "__main__":
    main()