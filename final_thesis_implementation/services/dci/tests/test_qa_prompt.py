from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.bcplus_eval.run_bcplus_eval import (
    DEFAULT_QA_PROMPT_TEMPLATE,
    build_benchmark_prompt,
)


class QaPromptTests(unittest.TestCase):
    def test_single_jsonl_prompt_uses_bounded_search_guidance(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            corpus = Path(td)
            (corpus / "wiki_dump.jsonl").touch()
            prompt = build_benchmark_prompt(
                "Who did it?", corpus, DEFAULT_QA_PROMPT_TEMPLATE
            )
            self.assertIn("one large JSONL file", prompt)
            self.assertIn("timeout 30s rg -n -i -F -m 5 -C 2", prompt)
            self.assertIn("Do not use the dedicated Read or Grep tools", prompt)
            self.assertIn("wiki_dump.jsonl", prompt)
            self.assertIn("Never request billions of lines", prompt)
            self.assertIn("final answer must appear in the tool evidence", prompt)
            self.assertIn("QUESTION:\nWho did it?", prompt)


if __name__ == "__main__":
    unittest.main()
