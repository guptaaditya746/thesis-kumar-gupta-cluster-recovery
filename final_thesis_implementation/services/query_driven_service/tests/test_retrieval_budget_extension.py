from __future__ import annotations

import json
import base64
import os
import subprocess
from pathlib import Path


def test_budget_extension_blocks_an_extra_tool_but_leaves_finalization_available():
    extension = (
        Path(__file__).parents[1]
        / "src"
        / "query_driven"
        / "pi_extensions"
        / "retrieval-budget.mjs"
    ).resolve()
    source = extension.read_text(encoding="utf-8").replace(
        'import { Type } from "@mariozechner/pi-ai";',
        "const Type = new Proxy({}, { get: () => (..._args) => ({}) });",
    )
    module_url = "data:text/javascript;base64," + base64.b64encode(
        source.encode("utf-8")
    ).decode("ascii")
    script = f"""
import extension from {json.dumps(module_url)};
let toolCall;
extension({{ registerTool() {{}}, on(name, handler) {{ if (name === "tool_call") toolCall = handler; }} }});
const first = await toolCall({{ toolName: "bash", input: {{ command: "rg term" }} }}, {{}});
const second = await toolCall({{ toolName: "bash", input: {{ command: "rg other" }} }}, {{}});
console.log(JSON.stringify({{ first: first ?? null, second }}));
"""
    env = {
        **os.environ,
        "QD_SEARCH_MAX_TOOLS": "1",
        "QD_SEARCH_MAX_SECONDS": "60",
    }

    completed = subprocess.run(
        ["node", "--input-type=module", "--eval", script],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    result = json.loads(completed.stdout)

    assert result["first"] is None
    assert result["second"]["block"] is True
    assert "final" in result["second"]["reason"].lower()
