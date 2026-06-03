#!/usr/bin/env python3
"""LAPTOP: Import desktop memories from shared/data/desktop-memories.json"""
import json, os, sqlite3
from hermes_roaming import (DATA_DIR, MEMORY_MD, USER_MD, SHARED,
                            content_hash, load_hashes, write_memory_file, preflight_check)

def import_desktop() -> str:
    preflight_check()

    export_path = os.path.join(DATA_DIR, "desktop-memories.json")
    if not os.path.exists(export_path):
        return _fallback_master_db()

    with open(export_path) as f:
        entries = json.load(f)

    stats = {"memory": 0, "user": 0}
    for target, local_path in [("memory", MEMORY_MD), ("user", USER_MD)]:
        existing_hashes, current_text = load_hashes(local_path)
        current_blocks = [b.strip() for b in current_text.split("§") if b.strip()]
        for entry in entries:
            if entry.get("target") != target:
                continue
            content = entry.get("content", "").strip()
            if content and content_hash(content) not in existing_hashes:
                current_blocks.append(content)
                existing_hashes.add(content_hash(content))
                stats[target] += 1
        if stats[target]:
            write_memory_file(local_path, current_blocks)

    return f"Imported from desktop: {stats['memory']} memory + {stats['user']} user"

def _fallback_master_db() -> str:
    master_db = os.path.join(SHARED, "master.db")
    if not os.path.exists(master_db):
        return "No master.db found. Skipping import."
    print(f"Master DB found ({os.path.getsize(master_db)} bytes).")
    print("Configure Hermes to use it:")
    print("  hermes config set memory.mnemosyne.shared_surface_path ~/.hermes/shared/master.db")
    return "OK"

if __name__ == "__main__":
    print(import_desktop())
