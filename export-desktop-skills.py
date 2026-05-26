#!/usr/bin/env python3
"""
DESKTOP SCRIPT — export-desktop-skills.py
Run by cron every 30 min (paired with import-laptop-skills on laptop side).
Walks ~/.hermes/skills/, collects all skills with their SKILL.md
and small supporting files, exports as JSON to Syncthing shared folder.
"""
import json, os, yaml
from datetime import datetime, timezone

SHARED = os.path.expanduser("~/.hermes/shared")
SKILLS_DIR = os.path.expanduser("~/.hermes/skills")

EXCLUDE_DIRS = {".hub", ".git", "__pycache__", ".stfolder"}
EXCLUDE_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".gif", ".mp3", ".mp4", ".wav", ".bin"}
MAX_FILE_SIZE = 100 * 1024


def parse_frontmatter(text):
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


def find_skills():
    skills = []
    for root, dirs, files in os.walk(SKILLS_DIR):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        if "SKILL.md" in files:
            rel_dir = os.path.relpath(root, SKILLS_DIR)
            skills.append((root, rel_dir))
    return skills


def collect_skill_files(skill_root):
    files = {}
    for dirpath, _, filenames in os.walk(skill_root):
        for fname in filenames:
            full_path = os.path.join(dirpath, fname)
            rel_path = os.path.relpath(full_path, skill_root)
            ext = os.path.splitext(fname)[1].lower()
            if ext in EXCLUDE_EXTENSIONS:
                continue
            try:
                size = os.path.getsize(full_path)
                if size > MAX_FILE_SIZE:
                    continue
            except OSError:
                continue
            try:
                with open(full_path, "r", encoding="utf-8") as f:
                    content = f.read()
                files[rel_path] = content
            except (UnicodeDecodeError, OSError):
                continue
    return files


def export():
    os.makedirs(SHARED, exist_ok=True)
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
        name = meta.get("name", rel_dir.replace("/", "-"))
        version = meta.get("version", "0.0.0")
        files = collect_skill_files(skill_root)
        export_data.append({
            "name": name,
            "version": version,
            "rel_dir": rel_dir,
            "skill_md": skill_md_text,
            "files": files,
            "exported_at": datetime.now(timezone.utc).isoformat(),
        })

    export_path = f"{SHARED}/desktop-skills.json"
    with open(export_path, "w", encoding="utf-8") as f:
        json.dump(export_data, f, ensure_ascii=False, indent=2)

    total_files = sum(len(s.get("files", {})) for s in export_data) + len(export_data)
    size_kb = os.path.getsize(export_path) / 1024
    return f"Exported {len(export_data)} skills ({total_files} files, {size_kb:.0f} KB) to desktop-skills.json"


if __name__ == "__main__":
    print(export())
