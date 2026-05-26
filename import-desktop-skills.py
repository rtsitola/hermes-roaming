#!/usr/bin/env python3
"""
DESKTOP SCRIPT — import-desktop-skills.py
Run by cron every 30 min (or on demand).
Reads laptop-skills.json from shared folder.
Merges laptop skills into ~/.hermes/skills/.
Version comparison: higher version wins. Same version → desktop keeps its own.
Creates new skills, updates outdated ones, skips unchanged.
Clears incoming file after successful merge.
"""
import json, os, shutil, yaml
from datetime import datetime


SHARED = os.path.expanduser("~/.hermes/shared")
SKILLS_DIR = os.path.expanduser("~/.hermes/skills")
INCOMING = f"{SHARED}/laptop-skills.json"

# Skills to NEVER overwrite from laptop (desktop is canonical for these)
# Add skill names here if desktop's version should always win.
PROTECTED_SKILLS = set()


def parse_version(v: str) -> tuple:
    """Parse semantic version string into comparable tuple."""
    try:
        parts = v.strip().split(".")
        return tuple(int(p) for p in parts[:3])
    except (ValueError, AttributeError):
        return (0, 0, 0)


def migrate_skill_dir(old_rel_dir: str, new_name: str) -> str:
    """
    If the skill was exported with a rel_dir that differs from its name,
    return the preferred directory for the new name. Usually the same.
    """
    # Use the skill name as the directory leaf, preserving category path
    parts = old_rel_dir.split("/")
    if len(parts) > 1:
        # Has category: e.g. devops/syncthing → keep category, use name as leaf
        return os.path.join(parts[0], new_name)
    return new_name


def install_skill(name: str, version: str, rel_dir: str, skill_md: str, files: dict):
    """Create a new skill directory and write all files."""
    dest_dir = os.path.join(SKILLS_DIR, rel_dir)
    os.makedirs(dest_dir, exist_ok=True)

    # Write SKILL.md
    with open(os.path.join(dest_dir, "SKILL.md"), "w", encoding="utf-8") as f:
        f.write(skill_md)

    # Write supporting files
    for fpath, content in files.items():
        full_path = os.path.join(dest_dir, fpath)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)

    return True


def merge():
    if not os.path.exists(INCOMING):
        return "Nothing to merge (no laptop-skills.json)."

    with open(INCOMING, "r", encoding="utf-8") as f:
        incoming_skills = json.load(f)

    if not incoming_skills:
        os.remove(INCOMING)
        return "Empty skills file, removed."

    stats = {"created": 0, "updated": 0, "skipped": 0, "protected": 0}

    for skill in incoming_skills:
        name = skill["name"]
        version = skill["version"]
        rel_dir = skill["rel_dir"]
        skill_md = skill.get("skill_md", "")
        files = skill.get("files", {})

        if name in PROTECTED_SKILLS:
            stats["protected"] += 1
            continue

        local_skill_md_path = os.path.join(SKILLS_DIR, rel_dir, "SKILL.md")

        if not os.path.exists(local_skill_md_path):
            # New skill — install it
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

        # Parse local version from frontmatter
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
            # Laptop has newer version — update
            skill_dir = os.path.dirname(local_skill_md_path)
            backup_dir = os.path.join(os.path.dirname(skill_dir),
                                      os.path.basename(skill_dir) + f".bak-{datetime.now().strftime('%Y%m%d-%H%M%S')}")
            shutil.move(skill_dir, backup_dir)

            install_skill(name, version, rel_dir, skill_md, files)
            shutil.rmtree(backup_dir, ignore_errors=True)
            stats["updated"] += 1
        else:
            stats["skipped"] += 1

    # Clear incoming file after successful merge
    os.remove(INCOMING)

    parts = []
    if stats["created"]:
        parts.append(f"{stats['created']} created")
    if stats["updated"]:
        parts.append(f"{stats['updated']} updated")
    if stats["skipped"]:
        parts.append(f"{stats['skipped']} skipped")
    if stats["protected"]:
        parts.append(f"{stats['protected']} protected")

    if not parts:
        return "No changes."
    return f"Merged skills: {', '.join(parts)}"


if __name__ == "__main__":
    print(merge())
