#!/usr/bin/env python3
"""
LAPTOP SCRIPT — import-laptop-skills.py
Run at START of laptop session (or on demand).
Reads desktop-skills.json from shared folder.
Merges desktop skills into ~/.hermes/skills/.
Version comparison: higher version wins. Same version → laptop keeps its own.
Creates new skills, updates outdated ones, skips unchanged.
Laptop custom skills (not from desktop) are preserved — only desktop-origin skills are updated.
Clears incoming file after successful merge.
"""
import json, os, shutil, yaml
from datetime import datetime


SHARED = os.path.expanduser("~/.hermes/shared")
SKILLS_DIR = os.path.expanduser("~/.hermes/skills")
INCOMING = f"{SHARED}/desktop-skills.json"


def parse_version(v: str) -> tuple:
    try:
        parts = v.strip().split(".")
        return tuple(int(p) for p in parts[:3])
    except (ValueError, AttributeError):
        return (0, 0, 0)


def install_skill(name: str, version: str, rel_dir: str, skill_md: str, files: dict):
    """Create a new skill directory and write all files."""
    dest_dir = os.path.join(SKILLS_DIR, rel_dir)
    os.makedirs(dest_dir, exist_ok=True)

    with open(os.path.join(dest_dir, "SKILL.md"), "w", encoding="utf-8") as f:
        f.write(skill_md)

    for fpath, content in files.items():
        full_path = os.path.join(dest_dir, fpath)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)

    return True


def merge():
    if not os.path.exists(INCOMING):
        return "Nothing to merge (no desktop-skills.json)."

    with open(INCOMING, "r", encoding="utf-8") as f:
        incoming_skills = json.load(f)

    if not incoming_skills:
        os.remove(INCOMING)
        return "Empty skills file, removed."

    stats = {"created": 0, "updated": 0, "skipped": 0}

    for skill in incoming_skills:
        name = skill["name"]
        version = skill["version"]
        rel_dir = skill["rel_dir"]
        skill_md = skill.get("skill_md", "")
        files = skill.get("files", {})

        local_skill_md_path = os.path.join(SKILLS_DIR, rel_dir, "SKILL.md")

        if not os.path.exists(local_skill_md_path):
            install_skill(name, version, rel_dir, skill_md, files)
            stats["created"] += 1
            continue

        # Skill exists locally — compare versions
        try:
            with open(local_skill_md_path, "r", encoding="utf-8") as f:
                local_text = f.read()
        except OSError:
            install_skill(name, version, rel_dir, skill_md, files)
            stats["created"] += 1
            continue

        local_version = "0.0.0"
        if local_text.startswith("---"):
            parts = local_text.split("---", 2)
            if len(parts) >= 3:
                try:
                    meta = yaml.safe_load(parts[1]) or {}
                    local_version = meta.get("version", "0.0.0")
                except yaml.YAMLError:
                    pass

        incoming_v = parse_version(version)
        local_v = parse_version(local_version)

        if incoming_v > local_v:
            skill_dir = os.path.dirname(local_skill_md_path)
            backup_dir = os.path.join(os.path.dirname(skill_dir),
                                      os.path.basename(skill_dir) + f".bak-{datetime.now().strftime('%Y%m%d-%H%M%S')}")
            shutil.move(skill_dir, backup_dir)
            install_skill(name, version, rel_dir, skill_md, files)
            shutil.rmtree(backup_dir, ignore_errors=True)
            stats["updated"] += 1
        else:
            stats["skipped"] += 1

    os.remove(INCOMING)

    parts = []
    if stats["created"]:
        parts.append(f"{stats['created']} created")
    if stats["updated"]:
        parts.append(f"{stats['updated']} updated")
    if stats["skipped"]:
        parts.append(f"{stats['skipped']} skipped")

    if not parts:
        return "No changes."
    return f"Merged skills: {', '.join(parts)}"


if __name__ == "__main__":
    print(merge())
