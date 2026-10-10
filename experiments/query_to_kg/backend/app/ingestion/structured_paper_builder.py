"""
Build structured paper JSON documents for Milestone 1.

This module converts one manifest record + parsed text + parsed sections
into a schema-valid PaperDocument.

M1-WI-08 output:
- backend/app/data/structured_papers/lightrag.json
- backend/app/data/structured_papers/autograph_r1.json
- backend/app/data/structured_papers/mind_the_query.json
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from backend.app.ingestion.schemas import PaperDocument, PaperMetadata, Section
from backend.app.ingestion import section_parser


def _first_present(record: dict[str, Any], keys: list[str]) -> Any:
    """
    Return the first non-empty value from a list of possible keys.

    This keeps the builder tolerant of small manifest naming differences,
    such as parsed_text vs parsed_text_path.
    """
    for key in keys:
        value = record.get(key)
        if value:
            return value
    return None


def _resolve_project_path(path_value: str | Path, project_root: Path) -> Path:
    """
    Convert a manifest path into an absolute Path.

    Manifest paths are usually relative to the project root.
    """
    path = Path(path_value)

    if path.is_absolute():
        return path

    return project_root / path


def get_parsed_text_path(
    paper_record: dict[str, Any],
    project_root: str | Path = ".",
) -> Path:
    """
    Get the parsed text path from a manifest record.
    """
    project_root = Path(project_root).resolve()

    parsed_text_value = _first_present(
        paper_record,
        ["parsed_text", "parsed_text_path"],
    )

    if not parsed_text_value:
        paper_id = paper_record.get("paper_id", "<unknown>")
        raise KeyError(
            f"Manifest record for paper '{paper_id}' is missing "
            "'parsed_text' or 'parsed_text_path'."
        )

    return _resolve_project_path(parsed_text_value, project_root)


def get_structured_json_path(
    paper_record: dict[str, Any],
    project_root: str | Path = ".",
) -> Path:
    """
    Get the structured JSON output path from a manifest record.
    """
    project_root = Path(project_root).resolve()

    structured_json_value = _first_present(
        paper_record,
        ["structured_json", "structured_json_path"],
    )

    if not structured_json_value:
        paper_id = paper_record.get("paper_id", "<unknown>")
        raise KeyError(
            f"Manifest record for paper '{paper_id}' is missing "
            "'structured_json' or 'structured_json_path'."
        )

    return _resolve_project_path(structured_json_value, project_root)


def _get_section_parser() -> Callable[..., Any]:
    """
    Find the section parser function from backend/app/ingestion/section_parser.py.

    The expected name is parse_sections, but this function also supports a few
    nearby names in case your implementation used slightly different naming.
    """
    candidate_function_names = [
        "parse_sections",
        "parse_paper_sections",
        "parse_document_sections",
        "parse_sections_from_text",
    ]

    for function_name in candidate_function_names:
        parser = getattr(section_parser, function_name, None)
        if callable(parser):
            return parser

    parser_class = getattr(section_parser, "SectionParser", None)
    if parser_class is not None:
        parser_instance = parser_class()

        for method_name in ["parse_sections", "parse", "parse_paper"]:
            method = getattr(parser_instance, method_name, None)
            if callable(method):
                return method

    raise AttributeError(
        "Could not find a section parser. Expected one of: "
        "parse_sections, parse_paper_sections, parse_document_sections, "
        "parse_sections_from_text, or SectionParser.parse_sections."
    )


def _call_section_parser(
    parser: Callable[..., Any],
    parsed_text: str,
    paper_id: str,
    paper_title: str,
) -> Any:
    """
    Call the section parser while tolerating small signature differences.
    """
    call_attempts = [
        lambda: parser(
            text=parsed_text,
            paper_id=paper_id,
            paper_title=paper_title,
        ),
        lambda: parser(
            text=parsed_text,
            paper_id=paper_id,
        ),
        lambda: parser(
            parsed_text=parsed_text,
            paper_id=paper_id,
            paper_title=paper_title,
        ),
        lambda: parser(
            parsed_text=parsed_text,
            paper_id=paper_id,
        ),
        lambda: parser(
            parsed_text,
            paper_id,
            paper_title,
        ),
        lambda: parser(
            parsed_text,
            paper_id,
        ),
        lambda: parser(parsed_text),
    ]

    errors: list[str] = []

    for attempt in call_attempts:
        try:
            return attempt()
        except TypeError as error:
            errors.append(str(error))

    raise TypeError(
        "Could not call the section parser with any supported signature. "
        f"Last errors: {errors[-3:]}"
    )


def _clean_title(title: Any) -> str:
    """
    Normalize section titles lightly.
    """
    if title is None:
        return "Untitled"

    cleaned = str(title).strip()
    cleaned = cleaned.lstrip("#").strip()

    return cleaned or "Untitled"


def _section_to_model(
    raw_section: Any,
    paper_id: str,
    order_fallback: int,
) -> Section:
    """
    Convert a parser section result into a Section schema object.

    Supports either:
    - Section objects
    - dictionaries
    - simple objects with attributes
    """
    if isinstance(raw_section, Section):
        section_data = raw_section.model_dump() if hasattr(raw_section, "model_dump") else raw_section.dict()

        section_data["paper_id"] = section_data.get("paper_id") or paper_id
        section_data["order"] = section_data.get("order", order_fallback)

        return Section(**section_data)

    if isinstance(raw_section, dict):
        section_id = raw_section.get("section_id") or raw_section.get("id")
        title = (
            raw_section.get("title")
            or raw_section.get("section_title")
            or raw_section.get("heading")
            or "Untitled"
        )
        text = (
            raw_section.get("text")
            or raw_section.get("section_text")
            or raw_section.get("content")
            or ""
        )
        level = raw_section.get("level", 1)
        order = raw_section.get("order", raw_section.get("section_order", order_fallback))

        page_start = raw_section.get("page_start")
        page_end = raw_section.get("page_end")

    else:
        section_id = getattr(raw_section, "section_id", None) or getattr(raw_section, "id", None)
        title = (
            getattr(raw_section, "title", None)
            or getattr(raw_section, "section_title", None)
            or getattr(raw_section, "heading", None)
            or "Untitled"
        )
        text = (
            getattr(raw_section, "text", None)
            or getattr(raw_section, "section_text", None)
            or getattr(raw_section, "content", None)
            or ""
        )
        level = getattr(raw_section, "level", 1)
        order = getattr(raw_section, "order", order_fallback)
        page_start = getattr(raw_section, "page_start", None)
        page_end = getattr(raw_section, "page_end", None)

    title = _clean_title(title)
    text = str(text).strip()

    if not section_id:
        section_id = f"{paper_id}_section_{order_fallback}"

    return Section(
        section_id=str(section_id),
        paper_id=paper_id,
        title=title,
        level=int(level or 1),
        order=int(order or order_fallback),
        text=text,
        page_start=page_start,
        page_end=page_end,
    )


def _normalize_sections(raw_sections: Any, paper_id: str) -> list[Section]:
    """
    Convert parser output into a clean list of Section objects.
    """
    if raw_sections is None:
        return []

    sections: list[Section] = []

    for index, raw_section in enumerate(raw_sections, start=1):
        section = _section_to_model(
            raw_section=raw_section,
            paper_id=paper_id,
            order_fallback=index,
        )

        if section.text.strip():
            sections.append(section)

    return sections


def extract_abstract(sections: list[Section]) -> str | None:
    """
    Extract abstract text from parsed sections when available.
    """
    for section in sections:
        normalized_title = section.title.strip().lower()

        if normalized_title == "abstract":
            return section.text.strip()

    return None


def extract_references(sections: list[Section]) -> list[dict[str, Any]]:
    """
    Extract a minimal references object when a references section exists.

    This does not try to split individual citations yet. That can happen later.
    For M1-WI-08, keeping the raw references text is enough and avoids
    overbuilding the parser.
    """
    references: list[dict[str, Any]] = []

    for section in sections:
        normalized_title = section.title.strip().lower()

        if normalized_title in {"references", "bibliography"}:
            references.append(
                {
                    "source_section_id": section.section_id,
                    "raw_text": section.text.strip(),
                }
            )

    return references


def build_structured_paper(
    paper_record: dict[str, Any],
    project_root: str | Path = ".",
) -> PaperDocument:
    """
    Build one PaperDocument from one manifest record.
    """
    project_root = Path(project_root).resolve()

    paper_id = paper_record["paper_id"]
    paper_title = paper_record["title"]

    parsed_text_path = get_parsed_text_path(
        paper_record=paper_record,
        project_root=project_root,
    )

    if not parsed_text_path.exists():
        raise FileNotFoundError(f"Parsed text file not found: {parsed_text_path}")

    parsed_text = parsed_text_path.read_text(encoding="utf-8").strip()

    if not parsed_text:
        raise ValueError(f"Parsed text file is empty: {parsed_text_path}")

    parser = _get_section_parser()
    raw_sections = _call_section_parser(
        parser=parser,
        parsed_text=parsed_text,
        paper_id=paper_id,
        paper_title=paper_title,
    )

    sections = _normalize_sections(
        raw_sections=raw_sections,
        paper_id=paper_id,
    )

    if not sections:
        raise ValueError(f"No non-empty sections were parsed for paper: {paper_id}")

    metadata = PaperMetadata(
        paper_id=paper_id,
        title=paper_title,
        authors=paper_record.get("authors") or [],
        year=paper_record.get("year"),
        venue=paper_record.get("venue"),
        source_pdf=paper_record.get("source_pdf"),
    )

    return PaperDocument(
        metadata=metadata,
        abstract=extract_abstract(sections),
        sections=sections,
        references=extract_references(sections),
    )


def _model_to_dict(model: Any) -> dict[str, Any]:
    """
    Serialize Pydantic v1 or v2 models to dictionaries.
    """
    if hasattr(model, "model_dump"):
        return model.model_dump(mode="json")

    if hasattr(model, "dict"):
        return model.dict()

    raise TypeError(f"Object is not a supported Pydantic model: {type(model)}")


def write_structured_paper(
    paper: PaperDocument,
    output_path: str | Path,
    project_root: str | Path = ".",
) -> Path:
    """
    Write one PaperDocument to a pretty JSON file.
    """
    project_root = Path(project_root).resolve()
    output_path = _resolve_project_path(output_path, project_root)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    data = _model_to_dict(paper)

    output_path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    return output_path
