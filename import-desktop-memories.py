#!/usr/bin/env python3
"""
LAPTOP SCRIPT — import-desktop-memories.py
Run at START of laptop session.
Copies desktop's MEMORY.md and USER.md from Syncthing share
into laptop's local ~/.hermes/memories/.
Only imports entries that don't already exist locally.
"""
import json, os, hashlib

SHARED = os.path.expanduser("~/.hermes/shared")
LOCAL_MEMORY = os.path.expanduser("~/.hermes/memories/MEMORY.md")
LOCAL_USER = os.path.expanduser("~/.hermes/memories/USER.md")

EXPORT_DESKTOP = f"{SHARED}/desktop-memories.json"

def content_hash(text):
    return hashlib.md5(text.strip().encode()).hexdigest()

def load_hashes(path):
    if not os.path.exists(path):
        return set()
    with open(path) as f:
        return {content_hash(b) for b in f.read().split("§") if b.strip()}

def import_desktop():
    # Check if desktop export exists
    if not os.path.exists(EXPORT_DESKTOP):
        # Fallback: read master.db directly via sqlite
        return try_import_from_master_db()
    
    with open(EXPORT_DESKTOP) as f:
        entries = json.load(f)
    
    memory_imported = 0
    user_imported = 0
    
    for target, local_path in [("memory", LOCAL_MEMORY), ("user", LOCAL_USER)]:
        existing = load_hashes(local_path)
        new_blocks = []
        
        for entry in entries:
            if entry.get("target") != target:
                continue
            content = entry.get("content", "").strip()
            if content and content_hash(content) not in existing:
                new_blocks.append(content)
                existing.add(content_hash(content))
        
        if new_blocks:
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            
            # Read current local
            current = ""
            if os.path.exists(local_path):
                with open(local_path) as f:
                    current = f.read()
            
            # Append new entries
            with open(local_path, "w") as f:
                f.write(current.strip())
                if current.strip():
                    f.write("\n§\n")
                f.write("\n§\n".join(new_blocks))
                f.write("\n")
            
            if target == "memory":
                memory_imported = len(new_blocks)
            else:
                user_imported = len(new_blocks)
    
    return f"Imported from desktop: {memory_imported} memory + {user_imported} user"

def try_import_from_master_db():
    """Fallback: try to extract from Mnemosyne master.db"""
    import sqlite3
    master_db = f"{SHARED}/master.db"
    if not os.path.exists(master_db):
        return "No master.db found. Skipping import."
    
    # Just signal that master.db is available for Mnemosyne
    print(f"Master DB found ({os.path.getsize(master_db)} bytes).")
    print("Configure Hermes to use it directly if needed:")
    print("  hermes config set memory.mnemosyne.shared_surface_path ~/.hermes/shared/master.db")
    return "OK"

if __name__ == "__main__":
    print(import_desktop())
