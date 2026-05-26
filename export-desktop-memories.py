#!/usr/bin/env python3
"""
DESKTOP SCRIPT — export-desktop-memories.py
Run after any memory change (or periodically).
Exports desktop's MEMORY.md + USER.md to shared/desktop-memories.json
so the laptop can import at session start.
"""
import json, os

SHARED = os.path.expanduser("~/.hermes/shared")
MEMORY_MD = os.path.expanduser("~/.hermes/memories/MEMORY.md")
USER_MD = os.path.expanduser("~/.hermes/memories/USER.md")
EXPORT_DESKTOP = f"{SHARED}/desktop-memories.json"

def export():
    entries = []
    
    for path, target in [(MEMORY_MD, "memory"), (USER_MD, "user")]:
        if not os.path.exists(path):
            continue
        with open(path) as f:
            for block in f.read().split("§"):
                block = block.strip()
                if block:
                    entries.append({"content": block, "target": target})
    
    with open(EXPORT_DESKTOP, "w") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)
    
    return f"Exported {len(entries)} entries to desktop-memories.json"

if __name__ == "__main__":
    print(export())
