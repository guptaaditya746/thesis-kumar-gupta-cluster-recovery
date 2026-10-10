#!/usr/bin/env python3
"""Evidence-oriented direct-vLLM acceptance probe.

This deliberately treats HTTP health as connectivity only.  A capability is
PASS only when the completion is complete, non-empty, and free of reasoning
tag leakage; tool tests additionally require a structured tool call.
"""
from __future__ import annotations

import argparse, json, os, re, subprocess, sys, time, urllib.error, urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

def gpu():
    try:
        out = subprocess.check_output(["nvidia-smi", "--query-gpu=memory.used,memory.free", "--format=csv,noheader,nounits"], text=True)
        used, free = out.strip().split(",")
        return {"used_mib": int(used), "free_mib": int(free)}
    except Exception as exc:
        return {"error": str(exc)}

def call(url, payload, key, stream=False, timeout=600):
    body = json.dumps(payload).encode()
    req = urllib.request.Request(url, body, {"Content-Type":"application/json", "Authorization":f"Bearer {key}"}, method="POST")
    started = time.perf_counter(); chunks = []
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            status = response.status
            if stream:
                for line in response:
                    chunks.append(line.decode(errors="replace"))
                raw = "".join(chunks)
                data = [json.loads(x[6:]) for x in raw.splitlines() if x.startswith("data: ") and x[6:] != "[DONE]"]
                return status, data, raw, time.perf_counter()-started
            raw = response.read().decode()
            return status, json.loads(raw), raw, time.perf_counter()-started
    except Exception as exc:
        return getattr(exc, "code", None), {"error": str(exc)}, "", time.perf_counter()-started

def result(kind, response, latency):
    choice = (response.get("choices") or [{}])[0]
    msg = choice.get("message") or {}
    content = msg.get("content") or ""
    reasoning = msg.get("reasoning_content", msg.get("reasoning", "")) or ""
    usage = response.get("usage") or {}
    failure = []
    if not content.strip(): failure.append("empty_final_content")
    if choice.get("finish_reason") == "length": failure.append("finish_reason_length")
    if re.search(r"</?think>", content, re.I): failure.append("think_tag_leak")
    return {"kind":kind, "pass": not failure, "failure": failure, "finish_reason":choice.get("finish_reason"), "content":content, "reasoning":reasoning, "tool_calls":msg.get("tool_calls"), "usage":usage, "latency_seconds":latency, "gpu_after":gpu()}

def main():
    p=argparse.ArgumentParser(); p.add_argument("--base-url", default="http://127.0.0.1:8002/v1"); p.add_argument("--model", default="qwen-chat"); p.add_argument("--key", default=os.environ.get("VLLM_API_KEY","sk-local-vllm")); p.add_argument("--prompt", default="Reply with exactly ACCEPTANCE_OK."); p.add_argument("--max-tokens", type=int, default=128); p.add_argument("--context-tokens", type=int, default=0); p.add_argument("--tokenizer", help="local/HF tokenizer; uses exact token count when supplied"); p.add_argument("--tools", action="store_true"); p.add_argument("--stream", action="store_true"); p.add_argument("--timeout", type=int, default=600); p.add_argument("--out", type=Path); a=p.parse_args()
    prompt = ("context " * max(0,a.context_tokens)) + "\n" + a.prompt
    actual_tokens = None
    if a.tokenizer:
        try:
            from transformers import AutoTokenizer
            tokenizer = AutoTokenizer.from_pretrained(a.tokenizer, local_files_only=True)
            unit = "context "
            prompt = (unit * max(0, a.context_tokens)) + "\n" + a.prompt
            actual_tokens = len(tokenizer.encode(prompt, add_special_tokens=False))
        except Exception as exc:
            print(json.dumps({"pass":False,"failure":["tokenizer_error"],"error":str(exc)})); return 1
    messages=[{"role":"user","content":prompt}]
    payload={"model":a.model,"messages":messages,"max_tokens":a.max_tokens,"temperature":0,"stream":a.stream}
    if a.tools:
        payload["tools"]=[{"type":"function","function":{"name":"lookup","description":"Look up a value","parameters":{"type":"object","properties":{"query":{"type":"string"}},"required":["query"]}}}]
        payload["tool_choice"]={"type":"function","function":{"name":"lookup"}}
    before=gpu(); status, data, raw, latency=call(a.base_url+"/chat/completions", payload, a.key, a.stream, a.timeout)
    if a.stream:
        final=data[-1] if data else {}; text="".join(((x.get("choices") or [{}])[0].get("delta") or {}).get("content") or "" for x in data); failures=[]
        if status != 200 or not data: failures.append("request_failure")
        if not text.strip(): failures.append("empty_final_content")
        if re.search(r"</?think>", text, re.I): failures.append("think_tag_leak")
        record={"kind":"stream","pass":not failures,"failure":failures,"status":status,"events":len(data),"content":text,"raw_sse":raw,"latency_seconds":latency,"gpu_before":before,"gpu_after":gpu()}
    else:
        record=result("tools" if a.tools else "chat", data, latency); record.update({"status":status,"gpu_before":before,"requested_context_tokens":a.context_tokens,"actual_prompt_tokens":actual_tokens,"max_tokens":a.max_tokens,"raw":raw})
        if status != 200: record["pass"]=False; record["failure"].append("request_failure")
        if a.tools and not record["tool_calls"]: record["pass"]=False; record["failure"].append("missing_tool_calls")
        if a.tools and record["tool_calls"]:
            for tool in record["tool_calls"]:
                if not tool.get("function", {}).get("name") or "arguments" not in tool.get("function", {}): record["pass"]=False; record["failure"].append("malformed_tool_call")
    record["timestamp"]=datetime.now().astimezone().isoformat(); record["model"]=a.model
    out=a.out or ROOT/"test_results"/"vllm-evidence"/datetime.now().strftime("%Y%m%d_%H%M%S")/f"{('stream' if a.stream else 'tools' if a.tools else 'chat')}_{a.context_tokens}.json"; out.parent.mkdir(parents=True,exist_ok=True); out.write_text(json.dumps(record,indent=2)+"\n"); print(json.dumps(record,indent=2)); return 0 if record["pass"] else 1
if __name__ == "__main__": sys.exit(main())
