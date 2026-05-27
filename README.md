# Hermes Roaming — Memory that travels with you

Hermes Agent memory sync across machines via Syncthing. Master-slave architecture — one desktop writes, laptops read and contribute.

## Architecture

```
Desktop (master, read/write)          Laptop (slave, read-only on master)
         │                                      │
         ├── master.db                           ├── scripts/import-desktop-memories.py
         ├── scripts/export-desktop-memories.py  ├── scripts/export-laptop-memories.py
         ├── scripts/export-desktop-skills.py    ├── scripts/import-desktop-skills.py
         ├── scripts/import-laptop-memories.py   ├── scripts/export-laptop-skills.py
         └── scripts/import-laptop-skills.py     └── local MEMORY.md / USER.md + skills/
         │                                      │
         └──────── Syncthing (P2P) ──────────────┘
              ~/.hermes/shared/ folder
              
  scripts/hermes_roaming.py — shared module (DRY)
  data/* — JSON/JSONL exports (auto-created)
```

## How it works

### Memory sync

1. **Desktop** exports → `data/desktop-memories.json` (periodic cron)
2. **Laptop** imports at session start → `python3 scripts/import-desktop-memories.py`
3. **Laptop** works, creates new memories locally
4. **Laptop** exports at session end → `python3 scripts/export-laptop-memories.py`
5. **Desktop** cron picks up `data/laptop-incoming.jsonl` → merges

### Skills sync

1. **Desktop** exports → `data/desktop-skills.json` (periodic cron)
2. **Laptop** imports at session start → `python3 scripts/import-desktop-skills.py`
3. **Laptop** creates/improves skills locally
4. **Laptop** exports at session end → `python3 scripts/export-laptop-skills.py`
5. **Desktop** cron picks up `data/laptop-skills.json` → merges (higher version wins)

Skills use semantic version comparison: higher version always wins. Same version → local copy is kept. Laptop skills are never downgraded by older desktop versions, and vice versa.

## Multi-machine

One master + N slaves. Each slave writes to its own `*-incoming.jsonl` (named by hostname). Desktop merges all of them. Syncthing mesh propagates files to all peers automatically.

## Prerequisites

- [Hermes Agent](https://github.com/NousResearch/hermes-agent) installed on all machines
- [Syncthing](https://syncthing.net/) installed on all machines
- Shared folder `~/.hermes/shared/` sync'd via Syncthing

## Quick Setup

### Desktop (master)

```bash
mkdir -p ~/.hermes/shared/scripts ~/.hermes/shared/data
cp master.db ~/.hermes/shared/
hermes config set memory.mnemosyne.shared_surface_path ~/.hermes/shared/master.db

# Cron: export + import every 30 min (memory + skills)
hermes cron create "every 30m" \
  --name "Sync Hermes memories and skills" \
  --toolsets terminal \
  --prompt "cd ~/.hermes/shared && python3 scripts/export-desktop-memories.py && python3 scripts/import-laptop-memories.py && python3 scripts/export-desktop-skills.py && python3 scripts/import-laptop-skills.py"
```

### Laptop (slave)

```bash
# Session start
cd ~/.hermes/shared
python3 scripts/import-desktop-memories.py
python3 scripts/import-desktop-skills.py

# ... work ...

# Session end
python3 scripts/export-laptop-memories.py
python3 scripts/export-laptop-skills.py
```

## What gets synced

| Asset | What | Sync method |
|-------|------|-------------|
| Memory | MEMORY.md + USER.md | Scripts (MD5 dedup) |
| Skills | SKILL.md + supporting files | Scripts (semver, higher wins) |
| Mnemosyne | master.db (vectors, triples) | Read-only on slaves, no merge |

## Limits

- Built-in memory only (~15 KB max)
- Skills: ~6 MB per export (excludes .hub cache, PDFs, files >100 KB)
- No session/conversation sync
- No multi-master (single source of truth)
- Latency: exports every 30 min via cron

## ⚠️ API Keys (.env) — NOT synced

The `.env` file containing API keys (DeepSeek, OpenRouter, GitHub, etc.) is **NOT included** in the Syncthing shared folder. This is intentional.

### Why

- Syncthing is P2P — every connected machine receives a copy of every file
- If one machine is compromised, all API keys are exposed
- `.env` files transmitted over relay servers could be intercepted (even though Syncthing encrypts transport, the file sits in plaintext on each peer)
- Third-party Syncthing relays are untrusted infrastructure

### Risks of syncing .env

| Risk | Severity |
|------|----------|
| API key leak if any machine is compromised | 🔴 Critical |
| All provider accounts accessible with leaked keys | 🔴 Critical |
| Usage billing on your accounts by attackers | 🔴 Critical |
| Relay server operator could read unencrypted file metadata | 🟡 Medium |

### Recommended approach

Copy `.env` **manually, once**, over a trusted channel:

```bash
# From desktop to laptop (SSH, USB, or secure transfer)
scp desktop:~/.hermes/.env ~/.hermes/.env
```

When you add a new API key on one machine, add it on the other manually. The `.env` file changes rarely — a few times a year at most.

**NEVER** add `~/.hermes/.env` to your Syncthing shared folder.

## License

MIT
