from __future__ import annotations

import shlex
import sys
from pathlib import Path
from typing import Any

from .config import ConfigError, LoadedConfig, get_bool, get_float, get_int, get_str, get_str_list


def _append(cmd: list[str], flag: str, value: Any | None) -> None:
    if value is not None:
        cmd.extend([flag, str(value)])


def _pi_paths(cfg: LoadedConfig) -> tuple[Path, Path]:
    pi = cfg.section("pi")
    package_dir = cfg.resolve_path(get_str(pi, "package_dir", "../pi_runtime/pi-mono/packages/coding-agent"))
    agent_dir = cfg.resolve_path(get_str(pi, "agent_dir", "../pi_runtime/pi-mono/.pi/agent"))
    assert package_dir is not None and agent_dir is not None
    return package_dir, agent_dir


def _add_common_pi_args(cmd: list[str], cfg: LoadedConfig, *, include_max_turns: bool = True) -> None:
    pi = cfg.section("pi")
    package_dir, agent_dir = _pi_paths(cfg)
    _append(cmd, "--package-dir", package_dir)
    _append(cmd, "--agent-dir", agent_dir)
    _append(cmd, "--provider", get_str(pi, "provider"))
    _append(cmd, "--model", get_str(pi, "model"))

    tools = pi.get("tools", ["read", "bash"])
    if isinstance(tools, list):
        if not all(isinstance(x, str) for x in tools):
            raise ConfigError("pi.tools must contain only strings")
        tools_value = ",".join(tools)
    elif isinstance(tools, str):
        tools_value = tools
    else:
        raise ConfigError("pi.tools must be a string or array of strings")
    if tools_value:
        _append(cmd, "--tools", tools_value)

    if include_max_turns:
        _append(cmd, "--max-turns", get_int(pi, "max_turns"))

    thinking = get_str(pi, "thinking")
    context_level = get_str(pi, "context_management_level")
    extra_args = get_str_list(pi, "extra_args")
    if thinking:
        extra_args.append(f"--thinking {thinking}")
    if context_level:
        extra_args.append(f"--context-management-level {context_level}")
    for extra in extra_args:
        cmd.append(f"--extra-arg={extra}")


def build_single_command(cfg: LoadedConfig) -> list[str]:
    run = cfg.section("run")
    cmd = [sys.executable, "-m", "dci.benchmark.pi_rpc_runner"]
    _add_common_pi_args(cmd, cfg)

    cwd = cfg.resolve_path(get_str(run, "cwd"))
    if cwd is None:
        raise ConfigError("[run].cwd is required for operation='single'")
    _append(cmd, "--cwd", cwd)

    output_dir = cfg.resolve_path(get_str(run, "output_dir"))
    if output_dir:
        _append(cmd, "--output-dir", output_dir)
    if get_bool(run, "resume", False):
        cmd.append("--resume")
    if get_bool(run, "keep_session", False):
        cmd.append("--keep-session")
    if get_bool(run, "show_tools", False):
        cmd.append("--show-tools")

    system_prompt = cfg.resolve_path(get_str(run, "system_prompt_file"))
    append_prompt = cfg.resolve_path(get_str(run, "append_system_prompt_file"))
    _append(cmd, "--system-prompt-file", system_prompt)
    _append(cmd, "--append-system-prompt-file", append_prompt)

    conv = cfg.section("conversation")
    if get_bool(conv, "clear_tool_results", False):
        cmd.append("--conversation-clear-tool-results")
        _append(cmd, "--conversation-clear-tool-results-keep-last", get_int(conv, "keep_last", 3))
    if get_bool(conv, "externalize_tool_results", False):
        cmd.append("--conversation-externalize-tool-results")
    if get_bool(conv, "strip_thinking", False):
        cmd.append("--conversation-strip-thinking")
    if get_bool(conv, "strip_usage", False):
        cmd.append("--conversation-strip-usage")

    eval_cfg = cfg.section("evaluation")
    gold = get_str(eval_cfg, "answer")
    gold_file = cfg.resolve_path(get_str(eval_cfg, "answer_file"))
    if gold and gold_file:
        raise ConfigError("Use only one of evaluation.answer or evaluation.answer_file")
    _append(cmd, "--eval-answer", gold)
    _append(cmd, "--eval-answer-file", gold_file)
    _append(cmd, "--eval-judge-model", get_str(eval_cfg, "judge_model"))
    _append(cmd, "--eval-judge-base-url", get_str(eval_cfg, "judge_base_url"))
    _append(cmd, "--eval-judge-api-key-env", get_str(eval_cfg, "judge_api_key_env"))
    _append(cmd, "--eval-judge-timeout-seconds", get_int(eval_cfg, "judge_timeout_seconds"))
    _append(cmd, "--eval-judge-input-price-per-1m", get_float(eval_cfg, "judge_input_price_per_1m"))
    _append(cmd, "--eval-judge-cached-input-price-per-1m", get_float(eval_cfg, "judge_cached_input_price_per_1m"))
    _append(cmd, "--eval-judge-output-price-per-1m", get_float(eval_cfg, "judge_output_price_per_1m"))

    question_file = cfg.resolve_path(get_str(run, "question_file"))
    question = get_str(run, "question")
    if question_file and question:
        raise ConfigError("Use only one of run.question or run.question_file")
    if question_file:
        _append(cmd, "--question-file", question_file)
    elif question:
        cmd.append(question)
    else:
        raise ConfigError("One of [run].question or [run].question_file is required")
    return cmd


def build_terminal_command(cfg: LoadedConfig) -> list[str]:
    run = cfg.section("run")
    cmd = [sys.executable, "-m", "dci.benchmark.pi_rpc_runner", "--terminal"]
    _add_common_pi_args(cmd, cfg, include_max_turns=False)
    cwd = cfg.resolve_path(get_str(run, "cwd"))
    if cwd is None:
        raise ConfigError("[run].cwd is required for operation='terminal'")
    _append(cmd, "--cwd", cwd)
    system_prompt = cfg.resolve_path(get_str(run, "system_prompt_file"))
    append_prompt = cfg.resolve_path(get_str(run, "append_system_prompt_file"))
    _append(cmd, "--system-prompt-file", system_prompt)
    _append(cmd, "--append-system-prompt-file", append_prompt)
    question_file = cfg.resolve_path(get_str(run, "question_file"))
    question = get_str(run, "question")
    if question_file:
        _append(cmd, "--question-file", question_file)
    elif question:
        cmd.append(question)
    return cmd


def build_benchmark_command(cfg: LoadedConfig) -> list[str]:
    bench = cfg.section("benchmark")
    pi = cfg.section("pi")
    eval_cfg = cfg.section("evaluation")
    script = cfg.service_root / "scripts" / "bcplus_eval" / "run_bcplus_eval.py"
    cmd = [sys.executable, str(script)]

    dataset = cfg.resolve_path(get_str(bench, "dataset"))
    output_root = cfg.resolve_path(get_str(bench, "output_root"))
    corpus_dir = cfg.resolve_path(get_str(bench, "corpus_dir"))
    if dataset is None or output_root is None or corpus_dir is None:
        raise ConfigError("benchmark.dataset, benchmark.output_root, and benchmark.corpus_dir are required")
    _append(cmd, "--dataset", dataset)
    _append(cmd, "--output-root", output_root)
    _append(cmd, "--corpus-dir", corpus_dir)

    package_dir, agent_dir = _pi_paths(cfg)
    _append(cmd, "--package-dir", package_dir)
    _append(cmd, "--agent-dir", agent_dir)
    _append(cmd, "--provider", get_str(pi, "provider"))
    _append(cmd, "--model", get_str(pi, "model"))

    tools = pi.get("tools", ["read", "bash"])
    if isinstance(tools, list):
        tools = ",".join(str(x) for x in tools)
    _append(cmd, "--tools", tools)
    _append(cmd, "--max-turns", get_int(pi, "max_turns"))
    _append(cmd, "--runtime-context-level", get_str(pi, "context_management_level"))
    _append(cmd, "--pi-thinking-level", get_str(pi, "thinking"))
    for extra in get_str_list(pi, "extra_args"):
        cmd.append(f"--pi-extra-arg={extra}")
    _append(cmd, "--node-max-old-space-size-mb", get_int(pi, "node_max_old_space_size_mb"))

    mode = get_str(bench, "mode", "qa")
    if mode not in {"qa", "ir"}:
        raise ConfigError("benchmark.mode must be 'qa' or 'ir'")
    if mode == "ir":
        cmd.append("--enable-ir")
        _append(cmd, "--corpus-hint", get_str(bench, "corpus_hint"))
    else:
        _append(
            cmd, "--qa-prompt-template",
            cfg.resolve_path(get_str(bench, "prompt_template")),
        )

    _append(cmd, "--max-concurrency", get_int(bench, "max_concurrency", 4))
    _append(cmd, "--limit", get_int(bench, "limit"))
    _append(cmd, "--system-prompt-file", cfg.resolve_path(get_str(bench, "system_prompt_file")))
    _append(cmd, "--append-system-prompt-file", cfg.resolve_path(get_str(bench, "append_system_prompt_file")))

    _append(cmd, "--judge-model", get_str(eval_cfg, "judge_model"))
    _append(cmd, "--judge-base-url", get_str(eval_cfg, "judge_base_url"))
    _append(cmd, "--judge-api-key-env", get_str(eval_cfg, "judge_api_key_env"))
    _append(cmd, "--judge-timeout-seconds", get_int(eval_cfg, "judge_timeout_seconds"))
    _append(cmd, "--judge-input-price-per-1m", get_float(eval_cfg, "judge_input_price_per_1m"))
    _append(cmd, "--judge-cached-input-price-per-1m", get_float(eval_cfg, "judge_cached_input_price_per_1m"))
    _append(cmd, "--judge-output-price-per-1m", get_float(eval_cfg, "judge_output_price_per_1m"))
    return cmd


def build_download_dataset_command(cfg: LoadedConfig) -> list[str]:
    data = cfg.section("data")
    script = cfg.service_root / "scripts" / "download_dci_bench.py"
    cmd = [sys.executable, str(script)]
    local_dir = cfg.resolve_path(get_str(data, "local_dir", "data/dci-bench"))
    _append(cmd, "--local-dir", local_dir)
    return cmd


def build_download_corpus_command(cfg: LoadedConfig) -> list[str]:
    data = cfg.section("data")
    script = cfg.service_root / "scripts" / "download_corpus.py"
    cmd = [sys.executable, str(script)]
    local_dir = cfg.resolve_path(get_str(data, "local_dir", "corpus"))
    _append(cmd, "--local-dir", local_dir)
    if get_bool(data, "skip_export", False):
        cmd.append("--skip-export")
    return cmd


def build_export_command(cfg: LoadedConfig, *, bright: bool) -> list[str]:
    data = cfg.section("data")
    if bright:
        cmd = [sys.executable, "-m", "dci.benchmark.export_bright_docs"]
        _append(cmd, "--source-root", cfg.resolve_path(get_str(data, "source_root")))
        _append(cmd, "--output-root", cfg.resolve_path(get_str(data, "output_root")))
        subsets = get_str_list(data, "subsets")
        for subset in subsets:
            cmd.extend(["--subset", subset])
        return cmd
    cmd = [sys.executable, "-m", "dci.benchmark.export_bc_plus_docs"]
    _append(cmd, "--source-dir", cfg.resolve_path(get_str(data, "source_dir")))
    _append(cmd, "--output-dir", cfg.resolve_path(get_str(data, "output_dir")))
    return cmd



def build_extract_bcplus_qa_command(cfg: LoadedConfig) -> list[str]:
    data = cfg.section("data")
    script = cfg.service_root / "scripts" / "bcplus_eval" / "extract_bcplus_qa.py"
    cmd = [sys.executable, str(script)]
    _append(cmd, "--parquet-dir", cfg.resolve_path(get_str(data, "parquet_dir")))
    _append(cmd, "--output", cfg.resolve_path(get_str(data, "output")))
    if get_bool(data, "no_decrypt", False):
        cmd.append("--no-decrypt")
    return cmd


def build_print_system_prompt_command(cfg: LoadedConfig) -> list[str]:
    pi = cfg.section("pi")
    run = cfg.section("run")
    package_dir, _ = _pi_paths(cfg)
    cmd = [sys.executable, "-m", "dci.benchmark.pi_system_prompt"]
    _append(cmd, "--package-dir", package_dir)
    _append(cmd, "--cwd", cfg.resolve_path(get_str(run, "cwd")))
    tools = pi.get("tools", ["read", "bash", "edit", "write"])
    if isinstance(tools, list):
        tools = ",".join(str(x) for x in tools)
    _append(cmd, "--tools", tools)
    _append(cmd, "--append-system-prompt-file", cfg.resolve_path(get_str(run, "append_system_prompt_file")))
    return cmd

def build_command(cfg: LoadedConfig) -> list[str]:
    operation = cfg.operation
    builders = {
        "single": build_single_command,
        "terminal": build_terminal_command,
        "benchmark": build_benchmark_command,
        "download_dataset": build_download_dataset_command,
        "download_corpus": build_download_corpus_command,
        "extract_bcplus_qa": build_extract_bcplus_qa_command,
        "print_system_prompt": build_print_system_prompt_command,
    }
    if operation in builders:
        return builders[operation](cfg)
    if operation == "export_bcplus":
        return build_export_command(cfg, bright=False)
    if operation == "export_bright":
        return build_export_command(cfg, bright=True)
    raise ConfigError(
        f"Unsupported operation {operation!r}. Expected one of: single, terminal, benchmark, "
        "download_dataset, download_corpus, extract_bcplus_qa, export_bcplus, export_bright, "
        "print_system_prompt"
    )


def shell_preview(cmd: list[str]) -> str:
    return " ".join(shlex.quote(part) for part in cmd)
