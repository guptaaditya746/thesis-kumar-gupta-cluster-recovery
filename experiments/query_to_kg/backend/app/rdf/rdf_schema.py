from backend.app.extraction.schemas import EdgeType, GraphPatch, NodeType

CLASS_NAMES = [
    "Paper",
    "Method",
    "Dataset",
    "Task",
    "Claim",
    "Evidence",
    "Limitation",
    "Metric",
    "Benchmark",
]

PREDICATE_NAMES = [
    "name",
    "title",
    "text",
    "description",
    "paperId",
    "paperTitle",
    "sectionTitle",
    "chunkId",
    "evidenceSpan",
    "proposes",
    "addressesTask",
    "usesMethod",
    "evaluatesOn",
    "reportsMetric",
    "makesClaim",
    "supportedBy",
    "hasLimitation",
    "describes",
    "comparesWith",
    "fromPaper",
    "fromChunk",
]

SCHEMA_PREFIXES = {
    "kg": "http://example.org/kg/",
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
}

NODE_TYPE_TO_CLASS_NAME = {
    NodeType.PAPER: "Paper",
    NodeType.METHOD: "Method",
    NodeType.DATASET: "Dataset",
    NodeType.TASK: "Task",
    NodeType.CLAIM: "Claim",
    NodeType.EVIDENCE: "Evidence",
    NodeType.LIMITATION: "Limitation",
    NodeType.METRIC: "Metric",
    NodeType.BENCHMARK: "Benchmark",
}

EDGE_TO_PREDICATE_NAME = {
    EdgeType.PROPOSES: "proposes",
    EdgeType.ADDRESSES_TASK: "addressesTask",
    EdgeType.USES_METHOD: "usesMethod",
    EdgeType.EVALUATES_ON: "evaluatesOn",
    EdgeType.REPORTS_METRIC: "reportsMetric",
    EdgeType.MAKES_CLAIM: "makesClaim",
    EdgeType.SUPPORTED_BY: "supportedBy",
    EdgeType.HAS_LIMITATION: "hasLimitation",
    EdgeType.DESCRIBES: "describes",
    EdgeType.COMPARES_WITH: "comparesWith",
    EdgeType.FROM_PAPER: "fromPaper",
    EdgeType.FROM_CHUNK: "fromChunk",
}

NODE_PROPERTY_TO_PREDICATE_NAME = {
    "name": "name",
    "title": "title",
    "text": "text",
    "description": "description",
}

PROVENANCE_TO_PREDICATE_NAME = {
    "paper_id": "paperId",
    "paper_title": "paperTitle",
    "section_title": "sectionTitle",
    "chunk_id": "chunkId",
    "text_span": "evidenceSpan",
}


def observed_classes(graph_patch: GraphPatch) -> list[str]:
    return sorted(
        {NODE_TYPE_TO_CLASS_NAME[node.type] for node in graph_patch.nodes},
        key=CLASS_NAMES.index,
    )


def observed_predicates(graph_patch: GraphPatch) -> list[str]:
    return sorted(
        {EDGE_TO_PREDICATE_NAME[edge.type] for edge in graph_patch.edges},
        key=PREDICATE_NAMES.index,
    )
