#!/usr/bin/env python3
"""
LAPTOP SCRIPT — export-laptop-memories.py
Run at END of laptop session.
Exports all laptop memories (built-in MEMORY.md + USER.md)
to the Syncthing shared folder as laptop-incoming.jsonl.
"""
import json, os
from datetime import datetime, timezone

SHARED = os.path.expanduser("~/.hermes/shared")
MEMORY_MD = os.path.expanduser("~/.hermes/memories/MEMORY.md")
USER_MD = os.path.expanduser("~/.hermes/memories/USER.md")

def parse_entries(path, target):
    """Parse MEMORY.md or USER.md into individual entries.
    Entries are separated by § or blank lines."""
    if not os.path.exists(path):
        return []
    
    with open(path) as f:
        text = f.read()
    
    # Split on § markers or double newlines
    entries = []
    for block in text.split("§"):
        block = block.strip()
        if block:
            entries.append({
                "content": block,
                "target": target,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
    return entries

def export():
    os.makedirs(SHARED, exist_ok=True)
    incoming_path = f"{SHARED}/laptop-incoming.jsonl"
    
    all_entries = []
    all_entries.extend(parse_entries(MEMORY_MD, "memory"))
    all_entries.extend(parse_entries(USER_MD, "user"))
    
    if not all_entries:
        return "No memories to export."
    
    with open(incoming_path, "w") as f:
        for entry in all_entries:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    
    return f"Exported {len(all_entries)} entries to laptop-incoming.jsonl"

if __name__ == "__main__":
    print(export())
