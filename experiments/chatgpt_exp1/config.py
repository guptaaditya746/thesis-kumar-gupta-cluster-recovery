# config.py
import argparse, os

def base_parser(**kwargs) -> argparse.ArgumentParser:
    """Returns a parser pre-loaded with shared connection args."""
    p = argparse.ArgumentParser(**kwargs)
    p.add_argument("--vllm-url",  default=os.getenv("VLLM_URL", "http://localhost:8000/v1"))
    p.add_argument("--model",     default=os.getenv("LLM_MODEL", "Qwen/Qwen2.5-3B-Instruct"))
    p.add_argument("--neo4j-uri", default=os.getenv("NEO4J_URI", "bolt://localhost:55677"))
    p.add_argument("--neo4j-user",default=os.getenv("NEO4J_USER", "neo4j"))
    p.add_argument("--neo4j-pass",default=os.getenv("NEO4J_PASS", "neo4j"))
    return p
