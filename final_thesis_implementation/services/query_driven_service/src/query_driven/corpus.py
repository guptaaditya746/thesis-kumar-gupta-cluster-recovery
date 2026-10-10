from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, Protocol

if TYPE_CHECKING:
    from .config import DatasetConfig


class InvalidDocumentReference(ValueError):
    """Raised when an agent-provided document reference cannot be trusted."""


@dataclass(frozen=True, slots=True)
class DocumentReference:
    kind: Literal["file", "jsonl_record"]
    path: Path
    document_id: str
    byte_offset: int | None = None

    def to_jsonable(self) -> dict[str, Any]:
        value: dict[str, Any] = {
            "kind": self.kind,
            "path": self.path.as_posix(),
            "document_id": self.document_id,
        }
        if self.byte_offset is not None:
            value["byte_offset"] = self.byte_offset
        return value


@dataclass(frozen=True, slots=True)
class CorpusDocument:
    reference: DocumentReference
    text: str

    @property
    def id(self) -> str:
        return self.reference.document_id


class CorpusAdapter(Protocol):
    root: Path

    def resolve(self, value: dict[str, Any]) -> CorpusDocument: ...

    def retrieval_instructions(self) -> str: ...

    def output_example(self) -> dict[str, Any]: ...

    def fingerprint(self) -> str: ...


class FileCorpusAdapter:
    def __init__(self, *, root: Path) -> None:
        self.root = root.resolve()
        if not self.root.is_dir():
            raise ValueError(f"corpus_root is not a directory: {self.root}")

    def resolve(self, value: dict[str, Any]) -> CorpusDocument:
        if value.get("kind") not in {None, "file"}:
            raise InvalidDocumentReference("Expected kind=file")
        raw_path = value.get("path")
        if not isinstance(raw_path, str) or not raw_path:
            raise InvalidDocumentReference("File reference requires path")
        candidate = Path(raw_path).expanduser()
        path = (
            candidate.resolve()
            if candidate.is_absolute()
            else (self.root / candidate).resolve()
        )
        try:
            relative_path = path.relative_to(self.root)
        except ValueError as exc:
            raise InvalidDocumentReference("File reference escapes corpus_root") from exc
        if not path.is_file():
            raise InvalidDocumentReference("File reference does not point to a document")

        document_id = path.stem
        supplied_id = value.get("document_id")
        if supplied_id is not None and str(supplied_id) != document_id:
            raise InvalidDocumentReference("File document_id does not match the filename")
        return CorpusDocument(
            reference=DocumentReference(
                kind="file",
                path=relative_path,
                document_id=document_id,
            ),
            text=path.read_text(encoding="utf-8", errors="replace"),
        )

    def retrieval_instructions(self) -> str:
        return """CORPUS LAYOUT:
- Each corpus document is a separate local file.
- Search with bounded rg/find commands, then read promising files.
- Return each selected document as kind=file with its relative path."""

    def output_example(self) -> dict[str, Any]:
        return {
            "kind": "file",
            "path": "relative/path.txt",
            "rank": 1,
            "reason": "Useful evidence.",
        }

    def fingerprint(self) -> str:
        stat = self.root.stat()
        return f"files:{self.root}:{stat.st_mtime_ns}"


class JsonlCorpusAdapter:
    def __init__(
        self,
        *,
        root: Path,
        corpus_file: str,
        id_field: str,
        content_field: str,
        max_record_bytes: int = 4 * 1024 * 1024,
    ) -> None:
        self.root = root.resolve()
        self.relative_path = Path(corpus_file)
        self.path = (self.root / self.relative_path).resolve()
        self.id_field = id_field
        self.content_field = content_field
        self.max_record_bytes = max_record_bytes

        try:
            self.relative_path = self.path.relative_to(self.root)
        except ValueError as exc:
            raise ValueError("JSONL corpus file must be inside corpus_root") from exc
        if not self.path.is_file():
            raise FileNotFoundError(f"JSONL corpus file was not found: {self.path}")

    def resolve(self, value: dict[str, Any]) -> CorpusDocument:
        if value.get("kind") != "jsonl_record":
            raise InvalidDocumentReference("Expected kind=jsonl_record")
        if Path(str(value.get("path", ""))) != self.relative_path:
            raise InvalidDocumentReference("JSONL reference points to the wrong corpus file")
        try:
            byte_offset = int(value["byte_offset"])
        except (KeyError, TypeError, ValueError) as exc:
            raise InvalidDocumentReference("JSONL reference requires an integer byte_offset") from exc
        if byte_offset < 0:
            raise InvalidDocumentReference("JSONL byte_offset must be non-negative")

        expected_id = str(value.get("document_id", ""))
        if not expected_id:
            raise InvalidDocumentReference("JSONL reference requires document_id")

        with self.path.open("rb") as handle:
            handle.seek(byte_offset)
            raw = handle.readline(self.max_record_bytes + 1)
        if not raw or len(raw) > self.max_record_bytes:
            raise InvalidDocumentReference("JSONL reference does not address one bounded record")
        try:
            record = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise InvalidDocumentReference("JSONL reference does not address valid JSON") from exc
        if not isinstance(record, dict):
            raise InvalidDocumentReference("JSONL record must be an object")

        actual_id = str(record.get(self.id_field, ""))
        if actual_id != expected_id:
            raise InvalidDocumentReference(
                f"JSONL document_id mismatch: expected {expected_id!r}, found {actual_id!r}"
            )
        content = record.get(self.content_field)
        if not isinstance(content, str):
            raise InvalidDocumentReference(
                f"JSONL record has no string field {self.content_field!r}"
            )

        return CorpusDocument(
            reference=DocumentReference(
                kind="jsonl_record",
                path=self.relative_path,
                document_id=actual_id,
                byte_offset=byte_offset,
            ),
            text=content,
        )

    def retrieval_instructions(self) -> str:
        return f"""CORPUS LAYOUT:
- The corpus contains one large JSONL file: {self.relative_path.as_posix()}.
- Each physical line is one independently addressable document record.
- Use the search_jsonl tool for this corpus. Do not use Bash, Read, cat, head, tail, rg, grep, or find on the JSONL file.
- For a named work, person, place, or organization, call search_jsonl with exact_title=true.
- Use exact_title=false only for a distinctive phrase when an exact record title is unavailable.
- Each tool result provides document_id and byte_offset as labeled machine-readable fields. Copy both values exactly into the final retrieval result.
- For multi-hop questions, preserve the first record reference, extract the intermediate entity from its preview, then search that entity with exact_title=true and return records verifying every hop.
- A two-hop final result normally contains at least the original-subject record and the intermediate-entity record. Do not return only the answer entity record unless that record itself explicitly states every required relation.
- Never search a generic relation word such as father, composer, song, or location by itself.
- Do not repeat an identical tool call; refine the entity or emit the final result."""

    def output_example(self) -> dict[str, Any]:
        return {
            "kind": "jsonl_record",
            "path": self.relative_path.as_posix(),
            "byte_offset": 12345,
            "document_id": "record-id",
            "rank": 1,
            "reason": "Useful evidence.",
        }

    def fingerprint(self) -> str:
        stat = self.path.stat()
        return f"jsonl:{self.relative_path}:{stat.st_size}:{stat.st_mtime_ns}"


def build_corpus_adapter(
    dataset: DatasetConfig,
    *,
    root: Path | None = None,
) -> CorpusAdapter:
    corpus_root = root or dataset.corpus_root
    if corpus_root is None:
        raise ValueError("dataset.corpus_root is required")
    if dataset.corpus_format == "jsonl":
        if not dataset.corpus_file:
            raise ValueError("dataset.corpus_file is required when corpus_format=jsonl")
        return JsonlCorpusAdapter(
            root=corpus_root,
            corpus_file=dataset.corpus_file,
            id_field=dataset.document_id_field,
            content_field=dataset.document_content_field,
            max_record_bytes=dataset.max_document_bytes,
        )
    return FileCorpusAdapter(root=corpus_root)
