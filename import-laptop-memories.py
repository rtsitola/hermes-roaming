#!/usr/bin/env python3
"""DESKTOP: Import laptop memories from shared/data/laptop-incoming.jsonl"""
import json, os
from hermes_roaming import (DATA_DIR, MEMORY_MD, USER_MD,
                            content_hash, load_hashes, write_memory_file,
                            preflight_check, MAX_MEMORY_CHARS, MAX_USER_CHARS)

def merge() -> str:
    preflight_check()

    incoming_path = os.path.join(DATA_DIR, "laptop-incoming.jsonl")
    if not os.path.exists(incoming_path):
        return "Nothing to merge."

    with open(incoming_path) as f:
        entries = [json.loads(line) for line in f if line.strip()]

    if not entries:
        os.remove(incoming_path)
        return "No valid entries."

    memory_entries = [e for e in entries if e.get("target") == "memory"]
    user_entries = [e for e in entries if e.get("target") == "user"]
    imported = {"memory": 0, "user": 0}

    for entries_list, path, max_chars, label in [
        (memory_entries, MEMORY_MD, MAX_MEMORY_CHARS, "memory"),
        (user_entries, USER_MD, MAX_USER_CHARS, "user"),
    ]:
        existing_hashes, current_text = load_hashes(path)
        current_blocks = [b.strip() for b in current_text.split("§") if b.strip()]
        for e in entries_list:
            c = e.get("content", "").strip()
            if c and content_hash(c) not in existing_hashes:
                current_blocks.append(c)
                existing_hashes.add(content_hash(c))
                imported[label] += 1

        if imported[label]:
            # Truncate oldest blocks if exceeding limit
            while current_blocks:
                candidate = "\n§\n".join(current_blocks)
                if len(candidate) <= max_chars:
                    break
                current_blocks.pop(0)  # remove oldest
            write_memory_file(path, current_blocks)

    os.remove(incoming_path)
    total = imported["memory"] + imported["user"]
    if total == 0:
        return "No new entries (all duplicates)."
    return f"Merged: {imported['memory']} memory + {imported['user']} user = {total} total"

if __name__ == "__main__":
    print(merge())
