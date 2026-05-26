#!/usr/bin/env python3
"""
DESKTOP SCRIPT — import-laptop-memories.py
Run by cron every 30 min.
Reads laptop-incoming.jsonl from shared folder.
Merges into ~/.hermes/memories/MEMORY.md and USER.md.
Deduplicates by content. Clears incoming file after merge.
"""
import json, os, hashlib
from datetime import datetime

SHARED = os.path.expanduser("~/.hermes/shared")
INCOMING = f"{SHARED}/laptop-incoming.jsonl"
MEMORY_MD = os.path.expanduser("~/.hermes/memories/MEMORY.md")
USER_MD = os.path.expanduser("~/.hermes/memories/USER.md")

MAX_MEMORY_CHARS = 4000
MAX_USER_CHARS = 2500

def content_hash(text):
    return hashlib.md5(text.strip().encode()).hexdigest()

def load_existing_hashes(path):
    """Load existing entries as set of content hashes."""
    if not os.path.exists(path):
        return set(), ""
    
    with open(path) as f:
        text = f.read()
    
    hashes = set()
    for block in text.split("§"):
        block = block.strip()
        if block:
            hashes.add(content_hash(block))
    return hashes, text

def merge():
    if not os.path.exists(INCOMING):
        return "Nothing to merge."
    
    # Read incoming entries
    entries = []
    with open(INCOMING) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    
    if not entries:
        return "No valid entries in incoming file."
    
    # Separate memory vs user
    memory_entries = [e for e in entries if e.get("target") == "memory"]
    user_entries = [e for e in entries if e.get("target") == "user"]
    
    imported = {"memory": 0, "user": 0}
    
    for entries_list, path, max_chars, target in [
        (memory_entries, MEMORY_MD, MAX_MEMORY_CHARS, "memory"),
        (user_entries, USER_MD, MAX_USER_CHARS, "user")
    ]:
        existing_hashes, current_text = load_existing_hashes(path)
        new_blocks = []
        
        for e in entries_list:
            content = e.get("content", "").strip()
            if content and content_hash(content) not in existing_hashes:
                new_blocks.append(content)
                existing_hashes.add(content_hash(content))
                imported[target] += 1
        
        if new_blocks:
            # Rebuild file: existing + new, respecting max chars
            all_blocks = [b.strip() for b in current_text.split("§") if b.strip()]
            all_blocks.extend(new_blocks)
            
            # Truncate oldest if exceeds limit (keep newest first)
            combined = ""
            for block in reversed(all_blocks):
                candidate = block + "§\n" + combined if combined else block
                if len(candidate) > max_chars:
                    break
                combined = "§\n" + block + "\n" + combined if combined else block
            
            combined = combined.strip()
            with open(path, "w") as f:
                f.write(combined + "\n")
    
    # Clear incoming file
    os.remove(INCOMING)
    
    total = imported["memory"] + imported["user"]
    if total == 0:
        return "No new entries (all duplicates)."
    return f"Merged: {imported['memory']} memory + {imported['user']} user = {total} total"

if __name__ == "__main__":
    print(merge())
