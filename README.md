# Hermes Roaming

Hermes Agent memory sync across machines via Syncthing. Master-slave architecture — one desktop writes, laptops read and contribute.

## Architecture

```
Desktop (master, read/write)          Laptop (slave, read-only on master)
         │                                      │
         ├── master.db                           ├── import-desktop-memories.py (session start)
         ├── export-desktop-memories.py          ├── export-laptop-memories.py (session end)
         └── import-laptop-memories.py           └── local MEMORY.md / USER.md
         │                                      │
         └──────── Syncthing (P2P) ──────────────┘
              ~/.hermes/shared/ folder
```

## How it works

1. **Desktop** exports `desktop-memories.json` periodically (cron)
2. **Laptop** imports it at session start → `python3 import-desktop-memories.py`
3. **Laptop** works, creates new memories locally
4. **Laptop** exports at session end → `python3 export-laptop-memories.py`
5. **Desktop** cron picks up `laptop-incoming.jsonl` → merges into master

## Multi-machine

One master + N slaves. Each slave writes to its own `*-incoming.jsonl` (named by hostname). Desktop merges all of them. Syncthing mesh propagates files to all peers automatically.

## Prerequisites

- [Hermes Agent](https://github.com/NousResearch/hermes-agent) installed on all machines
- [Syncthing](https://syncthing.net/) installed on all machines
- Shared folder `~/.hermes/shared/` sync'd via Syncthing

## Quick Setup

### Desktop (master)

```bash
mkdir -p ~/.hermes/shared
cp master.db ~/.hermes/shared/
hermes config set memory.mnemosyne.shared_surface_path ~/.hermes/shared/master.db

# Cron: export + import every 30 min
hermes cron create "every 30m" \
  --name "Sync Hermes memories" \
  --toolsets terminal \
  --prompt "python3 ~/.hermes/shared/export-desktop-memories.py && python3 ~/.hermes/shared/import-laptop-memories.py"
```

### Laptop (slave)

```bash
# Session start
python3 ~/.hermes/shared/import-desktop-memories.py

# ... work ...

# Session end
python3 ~/.hermes/shared/export-laptop-memories.py
```

## Memory levels

| Level | What | Sync method |
|-------|------|-------------|
| Built-in | MEMORY.md + USER.md | Scripts (recommended) |
| Mnemosyne | master.db (vectors, triples) | Read-only on slaves, no merge |

## Limits

- Built-in memory only (~15 KB max)
- No session/conversation sync
- No multi-master (single source of truth)
- Latency: exports every 30 min via cron

## License

MIT
