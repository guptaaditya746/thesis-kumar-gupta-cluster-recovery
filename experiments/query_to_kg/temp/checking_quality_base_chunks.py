import json
from pathlib import Path
from collections import defaultdict

path = Path("backend/app/data/chunks/base_chunks.jsonl")

if not path.exists():
    print(f"❌ Error: Cannot find file at {path}")
    exit(1)

# Tracking metrics
total_chunks = 0
papers = defaultdict(int)
sections = defaultdict(set)
chunk_ids = set()
duplicates = 0
missing_fields = defaultdict(int)

# Neighbor tracking maps
forward_links = {} # chunk_id -> next_chunk_id
backward_links = {} # chunk_id -> previous_chunk_id

required_keys = [
    "paper_id", "paper_title", "section_id", "section_title", 
    "chunk_id", "previous_chunk_id", "next_chunk_id", "raw_text"
]

for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
    if not line.strip():
        continue
    total_chunks += 1
    
    try:
        chunk = json.loads(line)
    except json.JSONDecodeError:
        print(f"❌ Line {i}: Invalid JSON syntax.")
        continue

    # 1. Field presence and empty check
    for key in required_keys:
        if key not in chunk:
            missing_fields[key] += 1
        elif chunk[key] is None or str(chunk[key]).strip() == "" or str(chunk[key]).lower() == "none":
            # Track if fields are explicitly empty/None strings
            if key not in ["previous_chunk_id", "next_chunk_id"]: 
                missing_fields[key] += 1

    # 2. Extract metrics
    p_id = chunk.get("paper_id", "unknown")
    s_id = chunk.get("section_id", "unknown")
    c_id = chunk.get("chunk_id", f"missing_id_line_{i}")

    papers[p_id] += 1
    if s_id != "unknown":
        sections[p_id].add(s_id)

    # 3. Check for duplicates
    if c_id in chunk_ids:
        duplicates += 1
    else:
        chunk_ids.add(c_id)

    # 4. Map neighbors
    forward_links[c_id] = chunk.get("next_chunk_id")
    backward_links[c_id] = chunk.get("previous_chunk_id")

# 5. Linkages Validation
broken_forward = 0
broken_backward = 0
isolated_chunks = 0

for c_id in chunk_ids:
    nxt = forward_links[c_id]
    prv = backward_links[c_id]
    
    # Treat string "None", true null/None, or empty as non-existent
    has_nxt = nxt and str(nxt).lower() != "none"
    has_prv = prv and str(prv).lower() != "none"

    if has_nxt and nxt not in chunk_ids:
        broken_forward += 1
    if has_prv and prv not in chunk_ids:
        broken_backward += 1
    if not has_nxt and not has_prv:
        isolated_chunks += 1

# --- REPORT ---
print("\n" + "="*50)
print("       BASE CHUNKS STRUCTURAL AUDIT REPORT")
print("="*50)
print(f"Total Chunks Scanned:       {total_chunks}")
print(f"Unique Paper IDs Found:     {len(papers)}")
print(f"Duplicate Chunk IDs:        {duplicates}")

print("\n--- Chunks Per Paper ---")
for p, count in papers.items():
    print(f"  • {p}: {count} chunks | {len(sections[p])} sections")

print("\n--- Missing / Blank Critical Fields ---")
if not missing_fields:
    print("  ✅ None! All core fields are populated.")
else:
    for f, count in missing_fields.items():
        print(f"  ⚠️ {f}: {count} missing value(s)")

print("\n--- Graph Neighborhood Integrity ---")
print(f"  • Broken forward links (next_chunk_id missing from file): {broken_forward}")
print(f"  • Broken backward links (previous_chunk_id missing from file): {broken_backward}")
print(f"  • Single-chunk / Isolated nodes (no neighbors at all):   {isolated_chunks}")
print("="*50 + "\n")
