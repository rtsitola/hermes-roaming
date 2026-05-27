#!/usr/bin/env python3
"""Export desktop memories to shared/data/desktop-memories.json"""
import json, os
from hermes_roaming import MEMORY_MD, USER_MD, DATA_DIR, parse_memory_entries

def export() -> str:
    all_entries = []
    all_entries.extend(parse_memory_entries(MEMORY_MD, "memory"))
    all_entries.extend(parse_memory_entries(USER_MD, "user"))
    if not all_entries:
        return "No memories to export."
    os.makedirs(DATA_DIR, exist_ok=True)
    path = os.path.join(DATA_DIR, "desktop-memories.json")
    with open(path, "w") as f:
        json.dump(all_entries, f, ensure_ascii=False, indent=2)
    return f"Exported {len(all_entries)} entries to desktop-memories.json"

if __name__ == "__main__":
    print(export())
