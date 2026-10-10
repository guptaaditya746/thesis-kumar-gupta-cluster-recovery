"""
docling_llamaindex_rag_pipeline.py

Purpose
-------
Build a simple RAG pipeline using:
- Docling for document ingestion/conversion
- LlamaIndex for indexing and retrieval
- Hugging Face embeddings for vectorization
- Milvus vector store for storage
- Hugging Face Inference API for generation

Why this matters for a thesis
-----------------------------
This script is useful for studying how document representation influences
retrieval quality in RAG and GraphRAG-style systems.

In particular, it allows you to compare:
1. Markdown-based parsing
2. Docling-native JSON parsing with richer metadata
3. Directory-based ingestion with SimpleDirectoryReader

This is important because richer document structure can improve:
- chunk quality,
- grounding,
- provenance,
- page-level evidence tracing,
- downstream graph construction.

Requirements
------------
pip install -q --progress-bar off --no-warn-conflicts \
    llama-index-core \
    llama-index-readers-docling \
    llama-index-node-parser-docling \
    llama-index-embeddings-huggingface \
    llama-index-llms-huggingface-api \
    llama-index-vector-stores-milvus \
    llama-index-readers-file \
    python-dotenv

If using notebooks, you may need to restart the kernel after installation.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from tempfile import mkdtemp
from typing import Any, List, Optional
from warnings import filterwarnings

import requests
from dotenv import load_dotenv


# -----------------------------------------------------------------------------
# Environment utilities
# -----------------------------------------------------------------------------

def get_env_from_colab_or_os(key: str) -> Optional[str]:
    """
    Try to load a secret from Google Colab first, then fall back to OS env vars.

    This is useful because experiments may run:
    - locally with .env
    - in Colab with userdata secrets
    """
    try:
        from google.colab import userdata
        try:
            return userdata.get(key)
        except userdata.SecretNotFoundError:
            pass
    except ImportError:
        pass

    return os.getenv(key)


def configure_environment() -> None:
    """
    Load environment variables and set a few warning / runtime preferences.
    """
    load_dotenv()

    filterwarnings(action="ignore", category=UserWarning, module="pydantic")
    filterwarnings(action="ignore", category=FutureWarning, module="easyocr")

    # Avoid noisy tokenizer parallelism warnings
    os.environ["TOKENIZERS_PARALLELISM"] = "false"


# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------

@dataclass
class RAGConfig:
    """
    Main experiment configuration.

    Modify these values to run different settings without changing core logic.
    """
    source: str = "https://arxiv.org/pdf/2408.09869"
    query: str = "Which are the main AI models in Docling?"
    embedding_model_name: str = "BAAI/bge-small-en-v1.5"
    generation_model_name: str = "mistralai/Mixtral-8x7B-Instruct-v0.1"
    hf_token_env_key: str = "HF_TOKEN"

    # Which pipeline variant to run:
    # "markdown", "docling_json", or "simple_directory"
    mode: str = "docling_json"

    # Output settings
    print_sources: bool = True
    max_source_preview_chars: int = 700


# -----------------------------------------------------------------------------
# Model and pipeline imports
# -----------------------------------------------------------------------------

from llama_index.core import StorageContext, VectorStoreIndex, SimpleDirectoryReader
from llama_index.core.node_parser import MarkdownNodeParser
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.llms.huggingface_api import HuggingFaceInferenceAPI
from llama_index.readers.docling import DoclingReader
from llama_index.vector_stores.milvus import MilvusVectorStore
from llama_index.node_parser.docling import DoclingNodeParser


# -----------------------------------------------------------------------------
# Model builders
# -----------------------------------------------------------------------------

def build_embedding_model(config: RAGConfig) -> HuggingFaceEmbedding:
    """
    Build the embedding model used for vector indexing.
    """
    return HuggingFaceEmbedding(model_name=config.embedding_model_name)


def build_generation_model(config: RAGConfig) -> HuggingFaceInferenceAPI:
    """
    Build the LLM used for answer generation.
    """
    hf_token = get_env_from_colab_or_os(config.hf_token_env_key)
    if not hf_token:
        raise ValueError(
            f"Missing Hugging Face token. Please set {config.hf_token_env_key} "
            "in your environment or Colab secrets."
        )

    return HuggingFaceInferenceAPI(
        token=hf_token,
        model_name=config.generation_model_name,
    )


def get_embedding_dimension(embed_model: HuggingFaceEmbedding) -> int:
    """
    Compute the output vector dimension from a sample embedding.

    Some vector stores need this explicitly.
    """
    sample_vector = embed_model.get_text_embedding("hi")
    return len(sample_vector)


# -----------------------------------------------------------------------------
# Vector store
# -----------------------------------------------------------------------------

def build_vector_store(embed_dim: int) -> MilvusVectorStore:
    """
    Create a Milvus vector store using a temporary local database path.

    For thesis experiments, you may want to replace this with a persistent path
    so you can compare runs or reuse the same index.
    """
    db_path = str(Path(mkdtemp()) / "docling.db")

    return MilvusVectorStore(
        uri=db_path,
        dim=embed_dim,
        overwrite=True,
    )


# -----------------------------------------------------------------------------
# Download helper for directory-based ingestion
# -----------------------------------------------------------------------------

def download_pdf_to_temp_dir(source_url: str) -> Path:
    """
    Download the source PDF into a temporary directory.

    This is used for the SimpleDirectoryReader example.
    """
    tmp_dir_path = Path(mkdtemp())

    response = requests.get(source_url, timeout=60)
    response.raise_for_status()

    output_file = tmp_dir_path / f"{Path(source_url).name}.pdf"
    with open(output_file, "wb") as f:
        f.write(response.content)

    return tmp_dir_path


# -----------------------------------------------------------------------------
# Reader / parser selection
# -----------------------------------------------------------------------------

def build_reader_and_parser(mode: str):
    """
    Return the appropriate reader and node parser for the selected mode.

    Modes
    -----
    markdown:
        Docling exports to Markdown, then MarkdownNodeParser handles chunking.

    docling_json:
        Docling exports rich JSON, then DoclingNodeParser uses the native
        structure and metadata.

    simple_directory:
        Uses the same reader/parser approach as above, but via SimpleDirectoryReader.
        In this script, we pair it with Docling JSON + DoclingNodeParser.
    """
    mode = mode.strip().lower()

    if mode == "markdown":
        reader = DoclingReader()
        node_parser = MarkdownNodeParser()
        return reader, node_parser

    if mode == "docling_json":
        reader = DoclingReader(export_type=DoclingReader.ExportType.JSON)
        node_parser = DoclingNodeParser()
        return reader, node_parser

    if mode == "simple_directory":
        reader = DoclingReader(export_type=DoclingReader.ExportType.JSON)
        node_parser = DoclingNodeParser()
        return reader, node_parser

    raise ValueError(
        f"Unsupported mode={mode!r}. Use 'markdown', 'docling_json', or 'simple_directory'."
    )


# -----------------------------------------------------------------------------
# Index building
# -----------------------------------------------------------------------------

def build_index_from_source(
    source: str,
    reader: Any,
    node_parser: Any,
    vector_store: MilvusVectorStore,
    embed_model: HuggingFaceEmbedding,
) -> VectorStoreIndex:
    """
    Build an index directly from the source using DoclingReader.
    """
    documents = reader.load_data(source)

    index = VectorStoreIndex.from_documents(
        documents=documents,
        transformations=[node_parser],
        storage_context=StorageContext.from_defaults(vector_store=vector_store),
        embed_model=embed_model,
    )
    return index


def build_index_from_directory(
    source: str,
    reader: Any,
    node_parser: Any,
    vector_store: MilvusVectorStore,
    embed_model: HuggingFaceEmbedding,
) -> VectorStoreIndex:
    """
    Build an index using SimpleDirectoryReader.

    This simulates a more realistic ingestion workflow where PDFs are stored
    in a local corpus directory.
    """
    tmp_dir = download_pdf_to_temp_dir(source)

    dir_reader = SimpleDirectoryReader(
        input_dir=tmp_dir,
        file_extractor={".pdf": reader},
    )

    documents = dir_reader.load_data()

    index = VectorStoreIndex.from_documents(
        documents=documents,
        transformations=[node_parser],
        storage_context=StorageContext.from_defaults(vector_store=vector_store),
        embed_model=embed_model,
    )
    return index


# -----------------------------------------------------------------------------
# Querying
# -----------------------------------------------------------------------------

def run_query(index: VectorStoreIndex, llm: Any, query: str):
    """
    Run a query against the index.
    """
    query_engine = index.as_query_engine(llm=llm)
    return query_engine.query(query)


# -----------------------------------------------------------------------------
# Source inspection
# -----------------------------------------------------------------------------

def preview_text(text: str, max_chars: int) -> str:
    """
    Create a short text preview for terminal-friendly display.
    """
    text = text.replace("\n", " ").strip()
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + " ..."


def print_result(result: Any, query: str, max_source_preview_chars: int = 700) -> None:
    """
    Print the query result and the retrieved source nodes.

    This is especially useful for analyzing:
    - retrieval quality
    - grounding evidence
    - metadata richness
    """
    print("\n" + "=" * 80)
    print(f"Q: {query}")
    print(f"A: {result.response.strip()}")
    print("=" * 80)

    if not hasattr(result, "source_nodes") or not result.source_nodes:
        print("\nNo source nodes returned.")
        return

    print("\nSources:")
    for i, node in enumerate(result.source_nodes, start=1):
        print(f"\n--- Source {i} ---")
        print("Text:")
        print(preview_text(node.text, max_source_preview_chars))

        print("\nMetadata:")
        metadata = getattr(node, "metadata", {})
        for key, value in metadata.items():
            print(f"  {key}: {value}")


# -----------------------------------------------------------------------------
# Thesis-oriented notes
# -----------------------------------------------------------------------------

def print_method_notes(mode: str) -> None:
    """
    Explain the chosen ingestion mode in a thesis-friendly way.
    """
    mode = mode.lower()

    print("\n" + "-" * 80)
    print("Method Notes")
    print("-" * 80)

    if mode == "markdown":
        print(
            "Markdown mode uses Docling to export the document into Markdown, then "
            "applies a MarkdownNodeParser. This is simple and readable, but some "
            "fine-grained structural metadata may be lost compared to Docling-native parsing."
        )
    elif mode == "docling_json":
        print(
            "Docling JSON mode preserves richer document structure and provenance. "
            "This is typically more suitable for advanced RAG and GraphRAG workflows "
            "because it retains metadata such as page-level grounding and other document-native signals."
        )
    elif mode == "simple_directory":
        print(
            "SimpleDirectoryReader mode simulates corpus-style ingestion from local files. "
            "This is useful when scaling from a single document experiment to a directory-based pipeline."
        )


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------

def main() -> None:
    config = RAGConfig()

    configure_environment()

    print("=" * 80)
    print("DOCLING + LLAMAINDEX RAG PIPELINE")
    print("=" * 80)
    print(f"Source document: {config.source}")
    print(f"Query          : {config.query}")
    print(f"Mode           : {config.mode}")
    print(f"Embedding model: {config.embedding_model_name}")
    print(f"LLM            : {config.generation_model_name}")

    # 1. Build models
    embed_model = build_embedding_model(config)
    gen_model = build_generation_model(config)

    # 2. Determine embedding dimension
    embed_dim = get_embedding_dimension(embed_model)
    print(f"Embedding dimension: {embed_dim}")

    # 3. Build vector store
    vector_store = build_vector_store(embed_dim)

    # 4. Select reader + parser
    reader, node_parser = build_reader_and_parser(config.mode)

    # 5. Build index
    if config.mode == "simple_directory":
        index = build_index_from_directory(
            source=config.source,
            reader=reader,
            node_parser=node_parser,
            vector_store=vector_store,
            embed_model=embed_model,
        )
    else:
        index = build_index_from_source(
            source=config.source,
            reader=reader,
            node_parser=node_parser,
            vector_store=vector_store,
            embed_model=embed_model,
        )

    # 6. Run query
    result = run_query(index=index, llm=gen_model, query=config.query)

    # 7. Print results
    print_result(
        result=result,
        query=config.query,
        max_source_preview_chars=config.max_source_preview_chars,
    )

    # 8. Print interpretation notes
    print_method_notes(config.mode)


if __name__ == "__main__":
    main()