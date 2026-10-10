from pydantic import BaseModel, Field

from backend.app.extraction.schemas import GraphPatch, ValidationReport


class GraphPatchCleanupResult(BaseModel):
    """Normalized graph patch plus cleanup and validation diagnostics."""

    patch: GraphPatch = Field(description="The cleaned, query-specific graph patch.")
    warnings: list[str] = Field(
        default_factory=list,
        description="Non-fatal cleanup actions and issues observed during normalization.",
    )
    validation_report: ValidationReport = Field(
        description="Validation report for the cleaned graph patch.",
    )
