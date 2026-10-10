from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from dci.service.command import build_command
from dci.service.config import ConfigError, load_config


class ServiceConfigTests(unittest.TestCase):
    def test_single_command_resolves_external_pi(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            config_text = """\
version = 1
operation = "single"

[pi]
package_dir = "../pi_runtime/pi-mono/packages/coding-agent"
agent_dir = "../pi_runtime/pi-mono/.pi/agent"
provider = "openai"
model = "test"

[run]
cwd = "corpus"
question = "hello"
"""
            (root / "config.toml").write_text(config_text, encoding="utf-8")
            cfg = load_config(root / "config.toml", service_root=root)
            cmd = build_command(cfg)
            joined = " ".join(cmd)
            self.assertIn("dci.benchmark.pi_rpc_runner", joined)
            self.assertIn(
                str((root.parent / "pi_runtime/pi-mono/packages/coding-agent").resolve()),
                joined,
            )
            self.assertEqual(cmd[-1], "hello")

    def test_benchmark_forwards_judge_base_url(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "config.toml").write_text(
                "version = 1\noperation = \"benchmark\"\n"
                "[benchmark]\ndataset = \"dataset.jsonl\"\noutput_root = \"output\"\ncorpus_dir = \"corpus\"\n"
                "[evaluation]\njudge_base_url = \"http://127.0.0.1:4000/v1\"\n",
                encoding="utf-8",
            )
            cfg = load_config(root / "config.toml", service_root=root)
            command = build_command(cfg)
            index = command.index("--judge-base-url")
            self.assertEqual(command[index + 1], "http://127.0.0.1:4000/v1")

    def test_qa_benchmark_forwards_prompt_template(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "config.toml").write_text(
                "version = 1\noperation = \"benchmark\"\n"
                "[benchmark]\ndataset = \"dataset.jsonl\"\noutput_root = \"output\"\n"
                "corpus_dir = \"corpus\"\nprompt_template = \"prompts/qa.j2\"\n",
                encoding="utf-8",
            )
            cfg = load_config(root / "config.toml", service_root=root)
            command = build_command(cfg)
            index = command.index("--qa-prompt-template")
            self.assertEqual(command[index + 1], str((root / "prompts/qa.j2").resolve()))


    def test_unknown_operation_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "config.toml").write_text(
                'version = 1\noperation = "wat"\n',
                encoding="utf-8",
            )
            cfg = load_config(root / "config.toml", service_root=root)
            with self.assertRaises(ConfigError):
                build_command(cfg)


if __name__ == "__main__":
    unittest.main()
