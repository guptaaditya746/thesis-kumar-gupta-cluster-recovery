# utils.py
import re

FORBIDDEN_TOKENS = {"CREATE","MERGE","DELETE","SET","CALL","APOC","LOAD","CSV"}

def contains_forbidden(cypher: str) -> bool:
    # token-based: avoids false positive "SET" inside "dataset"
    tokens = re.findall(r"[A-Z_]+", cypher.upper())
    return any(t in FORBIDDEN_TOKENS for t in tokens)
