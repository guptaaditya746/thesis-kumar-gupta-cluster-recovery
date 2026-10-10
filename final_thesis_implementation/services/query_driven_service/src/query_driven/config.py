from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10
    import tomli as tomllib  # type: ignore


Operation = Literal["pipeline", "pattern", "retrieval", "extraction", "construct", "inference", "evaluate"]


def _path(value: str | Path | None, *, base: Path) -> Path | None:
    if value is None or str(value).strip() == "":
        return None
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = base / path
    return path.resolve()


@dataclass(slots=True)
class LoggingConfig:
    level: str = "INFO"
    json: bool = False
    colors: bool = True
    file: Path | None = None


@dataclass(slots=True)
class TextModelConfig:
    kind: Literal["openai_compatible", "ollama_generate"] = "openai_compatible"
    endpoint: str = "http://localhost:8000/v1/chat/completions"
    model: str = "Qwen2.5-72B"
    api_key_env: str = "TEXT_MODEL_API_KEY"
    temperature: float = 0.0
    top_p: float = 1.0
    max_tokens: int = 1024
    timeout_seconds: float = 120.0
    extra_headers: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class EmbeddingConfig:
    enabled: bool = True
    endpoint: str = "http://localhost:11434/api/embeddings"
    model: str = "bge-m3"
    timeout_seconds: float = 120.0
    cache_dir: Path | None = None


@dataclass(slots=True)
class VisionConfig:
    enabled: bool = False
    endpoint: str = "http://localhost:11434/api/chat"
    model: str = "llava:34b"
    timeout_seconds: float = 120.0


@dataclass(slots=True)
class ImageSelectorConfig:
    kind: Literal["first", "gemini"] = "first"
    model: str = "gemini-1.5-flash"
    api_key_env: str = "GEMINI_API_KEY"


@dataclass(slots=True)
class ClipConfig:
    enabled: bool = False
    model: str = "CLIP-ViT-H-14-laion2B-s32B-b79K"
    top_k: int = 3
    device_map: str = "auto"


@dataclass(slots=True)
class DatasetConfig:
    format: Literal["mmqa", "webqa", "bright", "qa"] = "mmqa"
    name: str | None = None
    questions: Path | None = None
    texts: Path | None = None
    corpus_root: Path | None = None
    corpus_format: Literal["files", "jsonl"] = "files"
    corpus_file: str | None = None
    tables: Path | None = None
    images: Path | None = None
    image_root: Path | None = None
    image_description_dir: Path | None = None
    split: str | None = None
    qid_field: str = "qid"
    question_field: str = "question"
    text_id_field: str = "id"
    text_content_field: str = "text"
    document_id_field: str = "id"
    document_content_field: str = "text"
    max_document_bytes: int = 4 * 1024 * 1024
    answer_field: str = "answer"
    image_path_field: str = "path"
    image_title_field: str = "title"


@dataclass(slots=True)
class RuntimeConfig:
    operation: Operation = "pipeline"
    output_root: Path = Path("outputs/query_driven")
    cache_root: Path = Path("cache/query_driven")
    resume: bool = True
    overwrite: bool = False
    concurrency: int = 8
    max_questions: int | None = None
    max_refinement_iterations: int = 5
    initial_entity_count: int = 2
    table_entity_count: int = 1


@dataclass(slots=True)
class RetrievalConfig:
    enabled: bool = False
    source: Literal["corpus_root"] = "corpus_root"
    kind: Literal["agent"] = "agent"
    use_query_pattern: bool = True
    top_k: int = 20
    evaluation_k: int = 10
    max_search_turns: int = 50
    max_search_seconds: float = 300.0
    finalization_grace_seconds: float = 30.0
    show_tools: bool = False
    keep_session: bool = False
    forbid_gold_fields: list[str] = field(default_factory=list)


@dataclass(slots=True)
class AgentConfig:
    package_dir: Path
    agent_dir: Path
    provider: str = "vllm"
    model: str = "qwen-chat"
    tools: list[str] = field(default_factory=lambda: ["read", "bash"])
    max_turns: int = 100
    thinking: str = "high"
    context_management_level: str = "level3"
    node_max_old_space_size_mb: int = 8192
    max_output_tokens: int = 2048


@dataclass(slots=True)
class EvaluationConfig:
    enabled: bool = True
    kind: Literal["mmqa_answer", "answer_qa", "retrieval"] = "mmqa_answer"
    prediction_file: Path | None = None
    gold_file: Path | None = None
    gold_field: str = "gold_ids"
    prediction_field: str = "retrieved_ids"
    metrics: list[str] = field(default_factory=list)
    evaluate_answer: bool = True
    llm_judge: bool = False


@dataclass(slots=True)
class ServiceConfig:
    config_path: Path
    dataset: DatasetConfig
    runtime: RuntimeConfig
    logging: LoggingConfig
    text_model: TextModelConfig
    embedding: EmbeddingConfig
    vision: VisionConfig
    image_selector: ImageSelectorConfig
    clip: ClipConfig
    agent: AgentConfig
    retrieval: RetrievalConfig
    evaluation: EvaluationConfig

    def to_jsonable(self) -> dict[str, Any]:
        data = asdict(self)
        return _stringify_paths(data)


def _stringify_paths(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(k): _stringify_paths(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_stringify_paths(v) for v in value]
    return value


def _section(data: dict[str, Any], name: str) -> dict[str, Any]:
    section = data.get(name, {})
    if not isinstance(section, dict):
        raise ValueError(f"[{name}] must be a TOML table")
    return section


def load_config(path: str | Path) -> ServiceConfig:
    config_path = Path(path).expanduser().resolve()
    with config_path.open("rb") as handle:
        raw = tomllib.load(handle)
    base = config_path.parent

    dataset_raw = _section(raw, "dataset")
    runtime_raw = _section(raw, "runtime")
    logging_raw = _section(raw, "logging")
    text_raw = _section(raw, "text_model")
    embedding_raw = _section(raw, "embedding")
    vision_raw = _section(raw, "vision")
    selector_raw = _section(raw, "image_selector")
    clip_raw = _section(raw, "clip")
    agent_raw = _section(raw, "agent")
    retrieval_raw = _section(raw, "retrieval")
    eval_raw = _section(raw, "evaluation")

    dataset = DatasetConfig(
        **{
            **dataset_raw,
            "questions": _path(dataset_raw.get("questions"), base=base),
            "texts": _path(dataset_raw.get("texts"), base=base),
            "corpus_root": _path(dataset_raw.get("corpus_root"), base=base),
            "tables": _path(dataset_raw.get("tables"), base=base),
            "images": _path(dataset_raw.get("images"), base=base),
            "image_root": _path(dataset_raw.get("image_root"), base=base),
            "image_description_dir": _path(dataset_raw.get("image_description_dir"), base=base),
        }
    )
    runtime = RuntimeConfig(
        **{
            **runtime_raw,
            "output_root": _path(runtime_raw.get("output_root", "../outputs/query_driven"), base=base),
            "cache_root": _path(runtime_raw.get("cache_root", "../cache/query_driven"), base=base),
        }
    )
    logging_cfg = LoggingConfig(
        **{
            **logging_raw,
            "file": _path(logging_raw.get("file"), base=base),
        }
    )
    embedding = EmbeddingConfig(
        **{
            **embedding_raw,
            "cache_dir": _path(embedding_raw.get("cache_dir"), base=base),
        }
    )
    evaluation = EvaluationConfig(
        **{
            **eval_raw,
            "prediction_file": _path(eval_raw.get("prediction_file"), base=base),
            "gold_file": _path(eval_raw.get("gold_file"), base=base),
        }
    )

    agent = AgentConfig(
        **{
            **agent_raw,
            "package_dir": _path(
                agent_raw.get("package_dir", "../../../pi_runtime/pi-mono/packages/coding-agent"),
                base=base,
            ),
            "agent_dir": _path(
                agent_raw.get("agent_dir", "../../../pi_runtime/pi-mono/.pi/agent"),
                base=base,
            ),
        }
    )

    cfg = ServiceConfig(
        config_path=config_path,
        dataset=dataset,
        runtime=runtime,
        logging=logging_cfg,
        text_model=TextModelConfig(**text_raw),
        embedding=embedding,
        vision=VisionConfig(**vision_raw),
        image_selector=ImageSelectorConfig(**selector_raw),
        clip=ClipConfig(**clip_raw),
        agent=agent,
        retrieval=RetrievalConfig(**retrieval_raw),
        evaluation=evaluation,
    )
    validate_config(cfg)
    return cfg


def validate_config(cfg: ServiceConfig) -> None:
    if cfg.runtime.concurrency < 1:
        raise ValueError("runtime.concurrency must be >= 1")
    if cfg.runtime.max_refinement_iterations < 1:
        raise ValueError("runtime.max_refinement_iterations must be >= 1")
    if cfg.runtime.operation not in {"pipeline", "pattern", "retrieval", "extraction", "construct", "inference", "evaluate"}:
        raise ValueError(f"Unsupported runtime.operation: {cfg.runtime.operation}")
    if cfg.runtime.operation != "evaluate" and cfg.dataset.questions is None:
        raise ValueError("dataset.questions is required")
    if cfg.dataset.format in {"bright", "qa"} and cfg.runtime.operation in {"pipeline", "retrieval", "extraction", "construct", "inference"}:
        if cfg.dataset.texts is None and cfg.dataset.corpus_root is None:
            raise ValueError("dataset.texts or dataset.corpus_root is required for retrieval-based extraction/graph/inference")
    if cfg.dataset.corpus_format == "jsonl" and not cfg.dataset.corpus_file:
        raise ValueError("dataset.corpus_file is required when corpus_format=jsonl")
    if cfg.dataset.max_document_bytes < 1:
        raise ValueError("dataset.max_document_bytes must be >= 1")
    if cfg.dataset.format == "mmqa" and cfg.runtime.operation in {"pipeline", "extraction", "construct", "inference"}:
        if cfg.dataset.texts is None:
            raise ValueError("dataset.texts is required for MMQA extraction/graph/inference")
    if cfg.runtime.operation in {"pipeline", "construct", "inference"} and cfg.dataset.format == "mmqa":
        if cfg.dataset.tables is None:
            raise ValueError("dataset.tables is required for MMQA graph construction")
        if cfg.dataset.images is None:
            raise ValueError("dataset.images is required for MMQA graph construction/inference")
    if cfg.dataset.format in {"bright", "qa"} and cfg.runtime.operation in {"pipeline", "retrieval", "extraction", "construct", "inference"}:
        if cfg.dataset.corpus_root is None:
            raise ValueError("dataset.corpus_root is required for BRIGHT")
        if not cfg.retrieval.enabled:
            raise ValueError("retrieval.enabled must be true for BRIGHT")
    if cfg.retrieval.kind != "agent":
        raise ValueError("retrieval.kind must be agent; corpus-level embedding retrieval is not supported")
    if cfg.retrieval.top_k < 1 or cfg.retrieval.evaluation_k < 1 or cfg.retrieval.max_search_turns < 1:
        raise ValueError("retrieval top_k, evaluation_k, and max_search_turns must be >= 1")
    if cfg.retrieval.max_search_seconds <= 0 or cfg.retrieval.finalization_grace_seconds <= 0:
        raise ValueError("retrieval time and finalization budgets must be > 0")
    if cfg.agent.max_output_tokens < 1:
        raise ValueError("agent.max_output_tokens must be >= 1")
    if cfg.dataset.format in {"bright", "qa"} and cfg.runtime.operation in {"pipeline", "retrieval"}:
        if not cfg.agent.package_dir.exists():
            raise ValueError(f"agent.package_dir does not exist: {cfg.agent.package_dir}")
        if not cfg.agent.agent_dir.exists():
            raise ValueError(f"agent.agent_dir does not exist: {cfg.agent.agent_dir}")
    if cfg.runtime.operation == "evaluate":
        if cfg.evaluation.gold_file is None and cfg.dataset.questions is None:
            raise ValueError("evaluation.gold_file or dataset.questions is required for evaluation")


def dump_resolved_config(cfg: ServiceConfig, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cfg.to_jsonable(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
