#!/usr/bin/env python3
"""Export laptop memories to shared/data/laptop-incoming.jsonl"""
import json, os
from hermes_roaming import MEMORY_MD, USER_MD, DATA_DIR, parse_memory_entries

def export() -> str:
    all_entries = []
    all_entries.extend(parse_memory_entries(MEMORY_MD, "memory"))
    all_entries.extend(parse_memory_entries(USER_MD, "user"))
    if not all_entries:
        return "No memories to export."
    os.makedirs(DATA_DIR, exist_ok=True)
    path = os.path.join(DATA_DIR, "laptop-incoming.jsonl")
    with open(path, "w") as f:
        for entry in all_entries:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return f"Exported {len(all_entries)} entries to laptop-incoming.jsonl"

if __name__ == "__main__":
    print(export())
