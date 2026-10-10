from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from thesis_data_prep.settings import ResolvedConfig
from thesis_data_prep.utils import iter_files


@dataclass(frozen=True)
class ValidationResult:
    resource: str
    ok: bool
    details: dict[str, Any]
    errors: list[str]


def _validate_jsonl(path: Path, required_fields: set[str]) -> tuple[int, list[str]]:
    errors: list[str] = []
    records = 0
    seen_ids: set[str] = set()
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                errors.append(f"line {line_number}: invalid JSON: {exc}")
                if len(errors) >= 20:
                    break
                continue
            missing = required_fields.difference(record)
            if missing:
                errors.append(f"line {line_number}: missing fields {sorted(missing)}")
            query_id = record.get("query_id")
            if query_id is not None:
                query_id = str(query_id)
                if query_id in seen_ids:
                    errors.append(f"line {line_number}: duplicate query_id {query_id!r}")
                seen_ids.add(query_id)
            records += 1
            if len(errors) >= 20:
                break
    return records, errors


def validate_resource(settings: ResolvedConfig, resource_name: str) -> ValidationResult:
    resource = settings.resource(resource_name)
    output = settings.resource_output(resource_name)
    errors: list[str] = []
    details: dict[str, Any] = {
        "processor": resource.processor,
        "output": str(output),
    }

    if not output.exists() and not output.is_symlink():
        return ValidationResult(resource_name, False, details, [f"missing output: {output}"])

    if resource.processor in {"bcplus_qa", "publish_file"}:
        if not output.is_file():
            errors.append(f"expected a file: {output}")
        elif output.suffix == ".jsonl":
            required = {"query_id", "query", "answer"} if resource.processor == "bcplus_qa" else set()
            records, jsonl_errors = _validate_jsonl(output, required)
            details["records"] = records
            errors.extend(jsonl_errors)
            if resource.expected_min_records is not None and records < resource.expected_min_records:
                errors.append(
                    f"expected at least {resource.expected_min_records} records, found {records}"
                )
        else:
            details["bytes"] = output.stat().st_size
    elif resource.processor in {"browsecomp_docs", "bright_docs"}:
        marker = output / ".data_prep_complete.json"
        if not marker.is_file():
            errors.append(f"missing completion marker: {marker}")
        else:
            marker_payload = json.loads(marker.read_text(encoding="utf-8"))
            details["marker"] = marker_payload
            records = int(marker_payload.get("records", 0))
            if resource.expected_min_files is not None and records < resource.expected_min_files:
                errors.append(
                    f"expected at least {resource.expected_min_files} documents, marker reports {records}"
                )
            has_document = any(path.name != marker.name for path in iter_files(output))
            details["has_document_sample"] = has_document
            if records > 0 and not has_document:
                errors.append(f"completion marker reports documents, but output is empty: {output}")
    elif resource.processor == "publish_tree":
        if not output.is_dir():
            errors.append(f"expected a directory or directory symlink: {output}")
        else:
            sample_count = 0
            for _ in iter_files(output):
                sample_count += 1
                if sample_count >= 1000:
                    break
            details["sampled_files"] = sample_count
            if sample_count == 0:
                errors.append(f"published corpus is empty: {output}")

    return ValidationResult(resource_name, not errors, details, errors)
