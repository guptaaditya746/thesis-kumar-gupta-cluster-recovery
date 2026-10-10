"""
Parsed Text Generator

This module handles the extraction and normalization of text from PDF academic papers 
using a cascaded fallback approach with multiple parsers (LiteParse, Docling, PyMuPDF). 

HEAVY ASSUMPTIONS & HEURISTICS:
-------------------------------
1. Meaningful Length: A parsed text is only considered "meaningful" (successful) 
   if it yields at least 2,000 characters. PDFs producing less text are considered 
   parse failures.
2. Academic Structure Requirement: The parsed text MUST contain at least one of the 
   following structural keywords (case-insensitive): "abstract", "introduction", or 
   "references". If a document lacks these, the parse is rejected, and the next 
   parser in the chain is attempted.
3. Whitespace Normalization: Multiple consecutive blank lines are aggressively 
   collapsed into a single blank line to clean up standard PDF extraction artifacts.
4. Cascading Fallback: Parsers are attempted in a strict priority order (unless 
   overridden): LiteParse (CLI plain text) -> Docling (Markdown, preferred for 
   headings) -> PyMuPDF (basic page-by-page text fallback). The first parser to 
   produce "meaningful" text short-circuits the process.
"""

from __future__ import annotations

import json 
import shutil 
import subprocess 
from pathlib import Path 
from typing import Optional 


import fitz 

MIN_MEANINGFUL_CHARS = 2_000
MEANINGFUL_MARKERS = ("abstract", "introduction", "references")

def normalize_text(text: str) -> str:
    """
    Strips trailing/leading whitespace from lines and collapses multiple 
    consecutive blank lines into a single blank line.
    """
    lines = text.splitlines()

    cleaned_lines: list[str] = []
    previous_blank = False


    for line in lines:
        cleaned = line.strip()


        if not cleaned:
            if not previous_blank:
                cleaned_lines.append("")
            previous_blank  = True 
            continue 

        cleaned_lines.append(cleaned)
        previous_blank = False

    return "\n".join(cleaned_lines).strip() + "\n"



def is_meaningful_text(text: str) -> bool:
    """
    Evaluates text against strict heuristics (length and academic markers) 
    to determine if the PDF extraction was actually successful.
    """
    stripped = text.strip()

    if len(stripped) < MIN_MEANINGFUL_CHARS:
        return False

    lowered = stripped.lower()
    return any(marker in lowered for marker in MEANINGFUL_MARKERS)


def is_meaningful_file(path: Path) -> bool:
    """Checks if an existing output file passes the meaningfulness heuristics."""
    if not path.exists():
        return False
    
    text = path.read_text(encoding="utf-8", errors = "replace")
    return is_meaningful_text(text)


def write_if_meaningful(text: str, output_path: Path, parser_name: str) -> bool:
    """
    Normalizes text, evaluates its meaningfulness, and writes it to disk if it passes.
    Returns True if successfully written, False otherwise.
    """
    normalized = normalize_text(text)

    if not is_meaningful_text(normalized):
        return False
    
    output_path.parent.mkdir(parents = True, exist_ok = True)
    output_path.write_text(normalized, encoding="utf-8")


    print(f"[OK] Parsed with {parser_name}: {output_path}")
    print(f"    chars: {len(normalized)}")
    return True 


def parse_with_liteparse(pdf_path: Path, output_path: Path) -> bool:
    """Attempts to parse the PDF using the LiteParse CLI tool."""
    command = shutil.which("liteparse") or shutil.which("lit")

    if command is None:
        print("[SKIP] LiteParse command not found")
        return False

    try:
        result = subprocess.run(
            [
                command,
                str(pdf_path),
                "--format",
                "text",
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=180,
        )
    except subprocess.TimeoutExpired:
        print("[FAIL] LiteParse timed out")
        return False

    if result.returncode != 0:
        print("[FAIL] LiteParse failed")
        print(result.stderr[:1_000])
        return False

    return write_if_meaningful(result.stdout, output_path, "LiteParse")


def parse_with_docling(pdf_path: Path, output_path: Path) -> bool:
    """Attempts to parse the PDF using the docling library to extract Markdown."""
    try:
        from docling.document_converter import DocumentConverter
    except ImportError:
        print("[SKIP] Docling not installed")
        return False

    try:
        converter = DocumentConverter()
        result = converter.convert(str(pdf_path))

        # Markdown usually preserves headings better than plain text.
        text = result.document.export_to_markdown()
    except Exception as exc:
        print(f"[FAIL] Docling failed: {exc}")
        return False

    return write_if_meaningful(text, output_path, "Docling")

def parse_with_marker(pdf_path: Path, output_path: Path) -> bool:
    """
    TODO: Implementation missing. The 'text' variable is currently undefined.
    """

    return write_if_meaningful(result.stdout, output_path, "Marker")



def parse_with_pymupdf(pdf_path: Path, output_path: Path) -> bool:
    """Fallback parser that extracts raw text page-by-page using fitz."""
    try:
        page_texts: list[str] = []

        with fitz.open(pdf_path) as doc:
            for page_index, page in enumerate(doc, start=1):
                text = page.get_text("text").strip()

                if text:
                    page_texts.append(f"\n\n--- PAGE {page_index} ---\n\n{text}")

        combined_text = "\n".join(page_texts)
    except Exception as exc:
        print(f"[FAIL] PyMuPDF failed: {exc}")
        return False

    return write_if_meaningful(combined_text, output_path, "PyMuPDF")


def generate_parsed_text_for_paper(
    paper: dict,
    project_root: Path,
    preferred_parser: Optional[str] = None,
) -> bool:

    """
    Orchestrates the parsing of a single paper. Skips if a valid parsed file 
    already exists. Loops through available parsers until one produces meaningful text.
    """
    paper_id = paper["paper_id"]
    pdf_path = project_root / paper["source_pdf"]
    output_path = project_root / paper["parsed_text"]

    if is_meaningful_file(output_path):
        print(f"[SKIP] {paper_id}: existing parsed text is meaningful")
        return True

    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found for {paper_id}: {pdf_path}")

    print(f"[PARSE] {paper_id}")
    print(f"        PDF: {pdf_path}")
    print(f"        OUT: {output_path}")

    parser_order = ["liteparse", "docling", "pymupdf"]

    if preferred_parser:
        preferred_parser = preferred_parser.lower()
        parser_order = [preferred_parser] + [
            parser for parser in parser_order if parser != preferred_parser
        ]

    parser_functions = {
        "liteparse": parse_with_liteparse,
        "docling": parse_with_docling,
        "pymupdf": parse_with_pymupdf,
    }

    for parser_name in parser_order:
        parser_function = parser_functions[parser_name]

        if parser_function(pdf_path, output_path):
            return True

    print(f"[WARN] {paper_id}: no parser produced meaningful text")
    return False


def load_manifest(manifest_path: Path) -> list[dict]:
    """Loads and validates the manifest JSON file containing paper records."""
    with manifest_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError("manifest.json must contain a list of paper records")

    return data
