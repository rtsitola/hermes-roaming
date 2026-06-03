# Changelog

## [1.1.0] — 2026-06-03

### Fixed

- **Renamed memory import scripts** to follow the `import-{machine}-*.py` convention (same as skills scripts).
  - `import-desktop-memories.py` now runs on **Desktop** (was: Laptop)
  - `import-laptop-memories.py` now runs on **Laptop** (was: Desktop)
  - Content unchanged — only filenames swapped.

### Added

- Naming convention table in README.
- This changelog.

### Why this change

The original naming was inconsistent:
- Skills scripts: `import-desktop-*.py` = runs on Desktop ✅
- Memory scripts: `import-desktop-*.py` = runs on Laptop ❌ (opposite!)

This caused an 8-day sync bug (see FAQ below). Standardizing on `import-{machine}-*.py` = runs on `{machine}` eliminates the ambiguity.

---

## [1.0.0] — 2026-05-26

Initial release. Memory + skills sync via Syncthing.

---

## FAQ — The 8-Day Sync Bug (26 May → 3 June 2026)

### What happened?

Laptop skills were never arriving on the desktop. Every sync cycle appeared to
succeed ("Exported 130 skills") but the files vanished immediately after.

### Root cause

Three layers of confusion collided:

1. **Inconsistent naming.** Memory scripts used `import-desktop-*` to mean
   "imports desktop data" (runs on Laptop). Skills scripts used `import-desktop-*`
   to mean "runs on Desktop" (imports laptop data). Same prefix, opposite meaning.

2. **Silent self-destruction.** `import_skills_from()` in `hermes_roaming.py`
   calls `os.remove(filepath)` after importing — it deletes the source file.
   When the wrong script ran on the laptop, it read the freshly-exported
   `laptop-skills.json`, skipped everything (identical data), then deleted it.

3. **Misleading success output.** The script printed "130 skipped" — no error,
   no warning. The export script printed "Exported 130 skills" — also no error.
   Both appeared to succeed. Only a `find` after both scripts revealed the file
   was gone.

### Timeline

| Date | What happened | Why it didn't fix it |
|------|---------------|---------------------|
| May 26 | Skills sync scripts created with inconsistent naming | Nobody noticed the naming conflict |
| May 27 | Bug detected in watcher script (`hermes-roaming-import-laptop.py`) | Fixed the watcher, not the scripts themselves |
| May 28 | Same bug re-detected, cron updated | Fixed the cron, not the naming convention |
| May 29 | Cross-check via subagent confirmed "bug in watcher" | Partial fix again — watcher patched, scripts untouched |
| Jun 3 | Manual sync triggered the bug again | Finally traced to `os.remove()` + wrong script name |

### Why 5 sessions?

Each session fixed **one symptom** (the watcher, the cron, the auto-import
script) without addressing the **root cause** (inconsistent naming). It's like
fixing the phone number in your contacts when the real problem is that two
people share the same name.

### Lessons learned

1. **Fix at the right layer.** If the function has a confusing name, rename the
   function — don't just fix every caller one by one.

2. **`os.remove()` after import is dangerous.** When the wrong script reads the
   wrong file, the delete is silent and irreversible. Consider moving to a
   `.processed` suffix instead of deleting.

3. **"Skipped" is not "success".** When an import script reports only skips,
   it might be reading its own exports. Check the file system after every
   export/import cycle.

4. **One comprehensive fix > multiple partial patches.** A single commit that
   renames scripts + updates docs + updates crons would have caught this on
   day one.

5. **Cross-check the premise, not just the conclusion.** The subagent confirmed
   "the watcher is wrong" — but the premise ("the scripts are fine") was also
   wrong. Always verify the base assumption.

### How to prevent this

- The naming convention is now: **`import-{machine}-*.py` = runs on `{machine}`**
- Always consult the table in README before running a script manually
- After export, verify files exist: `ls -la ~/.hermes/shared/data/`
- After import, verify files are consumed (not just deleted)
