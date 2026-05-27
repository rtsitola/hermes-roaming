#!/usr/bin/env python3
"""
Hermes Roaming — Common module.
Shared functions used by all export/import scripts.
"""
import json, os, sys, hashlib, yaml
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

# ── Paths ──────────────────────────────────────────────────────────
SHARED = os.path.expanduser("~/.hermes/shared")
SKILLS_DIR = os.path.expanduser("~/.hermes/skills")
MEMORY_MD = os.path.expanduser("~/.hermes/memories/MEMORY.md")
USER_MD = os.path.expanduser("~/.hermes/memories/USER.md")

DATA_DIR = os.path.join(SHARED, "data")

# ── Skill export constants ─────────────────────────────────────────
EXCLUDE_DIRS = {".hub", ".git", "__pycache__", ".stfolder"}
EXCLUDE_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".gif", ".mp3", ".mp4", ".wav", ".bin"}
MAX_FILE_SIZE = 100 * 1024  # 100 KB

MAX_MEMORY_CHARS = 4000
MAX_USER_CHARS = 2500

# ── Hashing & dedup ────────────────────────────────────────────────

def content_hash(text: str) -> str:
    """MD5 hash of stripped content for deduplication."""
    return hashlib.md5(text.strip().encode()).hexdigest()


def load_hashes(path: str) -> tuple[set[str], str]:
    """Load existing entries as (set of hashes, raw text)."""
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


# ── Memory parsing ─────────────────────────────────────────────────

def parse_memory_entries(filepath: str, target: str) -> list[dict]:
    """Parse MEMORY.md or USER.md into entries with timestamps."""
    if not os.path.exists(filepath):
        return []
    with open(filepath) as f:
        text = f.read()
    entries = []
    for block in text.split("§"):
        block = block.strip()
        if block:
            entries.append({
                "content": block,
                "target": target,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
    return entries


def write_memory_file(path: str, blocks: list[str]) -> None:
    """Write blocks to MEMORY.md/USER.md separated by §."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write("\n§\n".join(blocks))
        f.write("\n")


# ── Skill helpers ──────────────────────────────────────────────────

def parse_frontmatter(text: str) -> tuple[dict, str]:
    """Extract YAML frontmatter. Returns (metadata_dict, body)."""
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    try:
        meta = yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError:
        meta = {}
    return meta, parts[2].strip()


def find_skills() -> list[tuple[str, str]]:
    """Walk SKILLS_DIR, find all skill directories. Returns [(root, rel_dir), ...]."""
    skills = []
    for root, dirs, files in os.walk(SKILLS_DIR):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        if "SKILL.md" in files:
            rel_dir = os.path.relpath(root, SKILLS_DIR)
            skills.append((root, rel_dir))
    return skills


def collect_skill_files(skill_root: str) -> dict[str, str]:
    """Collect all readable text files in a skill directory."""
    files = {}
    for dirpath, _, filenames in os.walk(skill_root):
        for fname in filenames:
            full_path = os.path.join(dirpath, fname)
            rel_path = os.path.relpath(full_path, skill_root)
            ext = os.path.splitext(fname)[1].lower()
            if ext in EXCLUDE_EXTENSIONS:
                continue
            try:
                if os.path.getsize(full_path) > MAX_FILE_SIZE:
                    continue
            except OSError:
                continue
            try:
                with open(full_path, "r", encoding="utf-8") as f:
                    files[rel_path] = f.read()
            except (UnicodeDecodeError, OSError):
                continue
    return files


def parse_version(v: str) -> tuple:
    """Parse semver string to comparable tuple."""
    try:
        parts = v.strip().split(".")
        return tuple(int(p) for p in parts[:3])
    except (ValueError, AttributeError):
        return (0, 0, 0)


def install_skill(name: str, version: str, rel_dir: str, skill_md: str, files: dict) -> bool:
    """Create/overwrite a skill directory with all supporting files."""
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


def get_local_version(skill_md_path: str) -> str:
    """Read version from a local SKILL.md frontmatter."""
    if not os.path.exists(skill_md_path):
        return "0.0.0"
    try:
        with open(skill_md_path, "r", encoding="utf-8") as f:
            text = f.read()
    except OSError:
        return "0.0.0"
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            try:
                meta = yaml.safe_load(parts[1]) or {}
                return meta.get("version", "0.0.0")
            except yaml.YAMLError:
                pass
    return "0.0.0"


# ── Pre-flight ─────────────────────────────────────────────────────

def preflight_check() -> None:
    """Run preflight diagnostics before any import. Non-fatal."""
    try:
        from preflight import check_ready
        issues = check_ready()
        if issues:
            print("❌ Prérequis manquants :")
            for i in issues:
                print(f"   {i}")
            print("⚠️  Continuation forcée...")
    except ImportError:
        print("⚠️  preflight.py introuvable — skip diagnostic")
    except Exception as e:
        print(f"⚠️  Erreur diagnostic: {e}")


# ── Common skill export logic ──────────────────────────────────────

def export_skills_to(filepath: str) -> str:
    """Export all skills to a JSON file. Returns status message."""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    skills = find_skills()
    if not skills:
        return "No skills found to export."

    export_data = []
    for skill_root, rel_dir in skills:
        skill_md_path = os.path.join(skill_root, "SKILL.md")
        try:
            with open(skill_md_path, "r", encoding="utf-8") as f:
                skill_md_text = f.read()
        except OSError:
            continue
        meta, _ = parse_frontmatter(skill_md_text)
        export_data.append({
            "name": meta.get("name", rel_dir.replace("/", "-")),
            "version": meta.get("version", "0.0.0"),
            "rel_dir": rel_dir,
            "skill_md": skill_md_text,
            "files": collect_skill_files(skill_root),
            "exported_at": datetime.now(timezone.utc).isoformat(),
        })

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(export_data, f, ensure_ascii=False, indent=2)

    total_files = sum(len(s.get("files", {})) for s in export_data) + len(export_data)
    size_kb = os.path.getsize(filepath) / 1024
    return f"Exported {len(export_data)} skills ({total_files} files, {size_kb:.0f} KB) to {os.path.basename(filepath)}"


# ── Common skill import logic ──────────────────────────────────────

def import_skills_from(filepath: str, protected: set | None = None) -> str:
    """Import skills from a JSON export, merging by version. Returns status message."""
    if protected is None:
        protected = set()

    if not os.path.exists(filepath):
        return f"Nothing to merge (no {os.path.basename(filepath)})."

    with open(filepath, "r", encoding="utf-8") as f:
        incoming_skills = json.load(f)

    if not incoming_skills:
        os.remove(filepath)
        return "Empty skills file, removed."

    stats = {"created": 0, "updated": 0, "skipped": 0, "protected": 0}

    for skill in incoming_skills:
        name = skill["name"]
        version = skill["version"]
        rel_dir = skill["rel_dir"]
        skill_md = skill.get("skill_md", "")
        files = skill.get("files", {})

        if name in protected:
            stats["protected"] += 1
            continue

        local_path = os.path.join(SKILLS_DIR, rel_dir, "SKILL.md")
        local_version = get_local_version(local_path)
        incoming_v = parse_version(version)
        local_v = parse_version(local_version)

        if not os.path.exists(local_path) or incoming_v > local_v:
            if os.path.exists(local_path):
                # Backup before overwriting
                import shutil
                skill_dir = os.path.dirname(local_path)
                backup_dir = os.path.join(os.path.dirname(skill_dir),
                    os.path.basename(skill_dir) + f".bak-{datetime.now().strftime('%Y%m%d-%H%M%S')}")
                shutil.move(skill_dir, backup_dir)
                install_skill(name, version, rel_dir, skill_md, files)
                shutil.rmtree(backup_dir, ignore_errors=True)
                stats["updated"] += 1
            else:
                install_skill(name, version, rel_dir, skill_md, files)
                stats["created"] += 1
        else:
            stats["skipped"] += 1

    os.remove(filepath)

    parts = []
    for key, label in [("created", "created"), ("updated", "updated"),
                        ("skipped", "skipped"), ("protected", "protected")]:
        if stats[key]:
            parts.append(f"{stats[key]} {label}")
    return f"Merged skills: {', '.join(parts)}" if parts else "No changes."
