#!/usr/bin/env python3
"""
Hermes Roaming — Diagnostic Machine
====================================

Vérifie que la machine est prête pour le roaming : Hermes, Mnemosyne,
Syncthing, espace disque, dépendances.

Génère un rapport JSON dans ~/.hermes/shared/diagnose-<hostname>.json
que l'autre machine peut lire pour comparer les configs.

Usage:
    python3 diagnose.py                # Check local + rapport
    python3 diagnose.py --json         # Sortie JSON uniquement
    python3 diagnose.py --check-peer   # Compare avec le rapport du pair
    python3 diagnose.py --quick        # Check rapide (sans Syncthing API)
"""

import json
import os
import sys
import socket
import shutil
import sqlite3
import subprocess
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ── Checks ──────────────────────────────────────────────────────────

def check_hermes() -> dict:
    """Vérifie l'installation Hermes."""
    result = {"ok": True, "issues": [], "details": {}}

    hermes_home = Path(os.path.expanduser("~/.hermes"))
    result["details"]["hermes_home"] = str(hermes_home)

    if not hermes_home.exists():
        result["ok"] = False
        result["issues"].append("~/.hermes introuvable — Hermes non installé ?")
        return result

    # Config
    config_path = hermes_home / "config.yaml"
    if config_path.exists():
        try:
            import yaml
            with open(config_path) as f:
                config = yaml.safe_load(f)
            result["details"]["model"] = config.get("model", {}).get("model", "?")
            result["details"]["provider"] = config.get("model", {}).get("provider", "?")
        except Exception:
            result["details"]["model"] = "error reading config"
    else:
        result["issues"].append("config.yaml absent")

    # Version via CLI
    try:
        r = subprocess.run(["hermes", "--version"], capture_output=True, text=True, timeout=10)
        if r.returncode == 0:
            result["details"]["version"] = r.stdout.strip()
        else:
            result["issues"].append("hermes --version a échoué")
    except FileNotFoundError:
        result["issues"].append("hermes CLI introuvable")
    except Exception as e:
        result["issues"].append(f"hermes CLI: {e}")

    # Profiles
    profiles_dir = hermes_home / "profiles"
    if profiles_dir.exists():
        result["details"]["profiles"] = [d.name for d in profiles_dir.iterdir() if d.is_dir()]

    # Skills
    skills_dir = hermes_home / "skills"
    if skills_dir.exists():
        result["details"]["skill_count"] = len(list(skills_dir.rglob("SKILL.md")))

    return result


def check_mnemosyne() -> dict:
    """Vérifie Mnemosyne."""
    result = {"ok": True, "issues": [], "details": {}}

    mnemosyne_db = Path(os.path.expanduser("~/.hermes/mnemosyne/data/mnemosyne.db"))

    if not mnemosyne_db.exists():
        result["ok"] = False
        result["issues"].append("MNEMOSYNE ABSENTE — mnemosyne.db introuvable. Installer avec: hermes memory setup")
        result["details"]["db_path"] = str(mnemosyne_db)
        result["details"]["db_exists"] = False
        return result

    result["details"]["db_path"] = str(mnemosyne_db)
    result["details"]["db_size_mb"] = round(mnemosyne_db.stat().st_size / (1024 * 1024), 2)
    result["details"]["db_exists"] = True

    try:
        conn = sqlite3.connect(str(mnemosyne_db))
        # Working memory count
        try:
            wm = conn.execute("SELECT COUNT(*) FROM working_memory").fetchone()[0]
            result["details"]["working_memories"] = wm
        except sqlite3.OperationalError:
            result["details"]["working_memories"] = "table missing"

        # Episodic
        try:
            ep = conn.execute("SELECT COUNT(*) FROM episodic_memory").fetchone()[0]
            result["details"]["episodic_memories"] = ep
        except sqlite3.OperationalError:
            result["details"]["episodic_memories"] = 0

        # Vector support
        try:
            vec = conn.execute("SELECT COUNT(*) FROM memory_vectors").fetchone()
            result["details"]["vectors"] = vec[0] if vec else 0
        except sqlite3.OperationalError:
            result["details"]["vectors"] = "not available"

        conn.close()
    except Exception as e:
        result["ok"] = False
        result["issues"].append(f"Erreur connexion Mnemosyne: {e}")

    return result


def check_syncthing(quick: bool = False) -> dict:
    """Vérifie Syncthing."""
    result = {"ok": True, "issues": [], "details": {}}

    # Dossier shared
    shared_dir = Path(os.path.expanduser("~/.hermes/shared"))
    result["details"]["shared_dir"] = str(shared_dir)
    result["details"]["shared_exists"] = shared_dir.exists()

    if not shared_dir.exists():
        result["ok"] = False
        result["issues"].append("~/.hermes/shared/ absent — Syncthing non configuré ?")
        return result

    # Fichiers clés
    key_files = ["master.db", "export-desktop-memories.py", "import-laptop-memories.py"]
    for kf in key_files:
        exists = (shared_dir / kf).exists()
        result["details"][f"has_{kf.replace('.','_').replace('-','_')}"] = exists
        if not exists:
            result["issues"].append(f"{kf} absent du dossier shared/")

    # .stfolder (indicateur Syncthing)
    stfolder = shared_dir / ".stfolder"
    result["details"]["syncthing_active"] = stfolder.exists()

    if quick:
        return result

    # API Syncthing
    try:
        api_key = _get_syncthing_api_key()
        if api_key:
            import urllib.request
            req = urllib.request.Request(
                "http://localhost:8384/rest/system/status",
                headers={"X-API-Key": api_key},
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                status = json.loads(resp.read())
            result["details"]["syncthing_version"] = status.get("version", "?")
            result["details"]["syncthing_uptime"] = status.get("uptime", 0)
        else:
            result["details"]["syncthing_api"] = "clé API introuvable"
    except Exception as e:
        result["details"]["syncthing_api"] = f"inaccessible: {e}"
        result["issues"].append("API Syncthing inaccessible (localhost:8384)")

    # Devices
    try:
        config_xml = _find_syncthing_config()
        if config_xml and config_xml.exists():
            # Quick parse — count devices
            content = config_xml.read_text()
            device_count = content.count("<device ")
            result["details"]["syncthing_devices"] = device_count
    except Exception:
        pass

    return result


def _get_syncthing_api_key() -> Optional[str]:
    """Extrait la clé API Syncthing."""
    import re
    config = _find_syncthing_config()
    if not config or not config.exists():
        return None
    try:
        content = config.read_text()
        match = re.search(r"<apikey>(.+?)</apikey>", content)
        return match.group(1) if match else None
    except Exception:
        return None


def _find_syncthing_config() -> Optional[Path]:
    """Trouve le fichier config.xml de Syncthing."""
    candidates = [
        Path(os.path.expanduser("~/.local/state/syncthing/config.xml")),
        Path(os.path.expanduser("~/.config/syncthing/config.xml")),
    ]
    # Windows (WSL)
    localappdata = os.environ.get("LOCALAPPDATA", "")
    if localappdata:
        candidates.append(Path(localappdata) / "Syncthing" / "config.xml")
    # Fallback: chercher dans /mnt/c
    wsl_config = Path("/mnt/c/Users")
    if wsl_config.exists():
        for user_dir in wsl_config.iterdir():
            candidate = user_dir / "AppData" / "Local" / "Syncthing" / "config.xml"
            if candidate.exists():
                candidates.append(candidate)

    for c in candidates:
        if c.exists():
            return c
    return None


def check_environment() -> dict:
    """Vérifie l'environnement système."""
    result = {"ok": True, "issues": [], "details": {}}

    result["details"]["hostname"] = socket.gethostname()
    result["details"]["os"] = os.uname().sysname if hasattr(os, "uname") else os.name

    # Python
    result["details"]["python_version"] = sys.version.split()[0]
    result["details"]["python_executable"] = sys.executable

    # Python 3.12+ requis pour datetime.utcnow() deprecation
    py_ver = tuple(map(int, sys.version.split(".")[:2]))
    if py_ver < (3, 9):
        result["issues"].append(f"Python {sys.version.split()[0]} — 3.9+ recommandé")

    # Disk space
    try:
        home_usage = shutil.disk_usage(os.path.expanduser("~"))
        result["details"]["disk_home_free_gb"] = round(home_usage.free / (1024**3), 1)
        result["details"]["disk_home_total_gb"] = round(home_usage.total / (1024**3), 1)

        if home_usage.free < 500 * 1024 * 1024:  # < 500 MB
            result["issues"].append(f"Espace disque faible : {result['details']['disk_home_free_gb']} GB libres")
    except Exception:
        pass

    # Check H: drive (WSL)
    h_drive = Path("/mnt/h")
    if h_drive.exists():
        try:
            h_usage = shutil.disk_usage("/mnt/h")
            result["details"]["disk_h_free_gb"] = round(h_usage.free / (1024**3), 1)
        except Exception:
            pass

    # Hermes shared folder disk
    shared_dir = Path(os.path.expanduser("~/.hermes/shared"))
    if shared_dir.exists():
        try:
            shared_usage = shutil.disk_usage(str(shared_dir))
            result["details"]["shared_files"] = len(list(shared_dir.iterdir()))
        except Exception:
            pass

    return result


def check_shared_master() -> dict:
    """Vérifie l'accès à master.db dans shared/."""
    result = {"ok": True, "issues": [], "details": {}}

    master_db = Path(os.path.expanduser("~/.hermes/shared/master.db"))

    if not master_db.exists():
        result["ok"] = False
        result["issues"].append("master.db absent — contacter le maître (desktop)")
        result["details"]["master_db"] = str(master_db)
        return result

    result["details"]["master_db"] = str(master_db)
    result["details"]["master_db_size_mb"] = round(master_db.stat().st_size / (1024 * 1024), 2)

    try:
        conn = sqlite3.connect(str(master_db))
        wm = conn.execute("SELECT COUNT(*) FROM working_memory").fetchone()[0]
        result["details"]["master_working_memories"] = wm
        conn.close()
    except Exception as e:
        result["issues"].append(f"master.db inaccessible: {e}")

    # Test écriture
    test_file = master_db.parent / ".write_test"
    try:
        test_file.write_text("test")
        test_file.unlink()
        result["details"]["write_test"] = True
    except Exception:
        result["details"]["write_test"] = False
        result["issues"].append("Impossible d'écrire dans shared/ — permissions ?")

    return result


# ── Peer comparison ─────────────────────────────────────────────────

def compare_with_peer(shared_dir: str) -> dict:
    """Compare son diagnostic avec celui du pair."""
    shared = Path(shared_dir)
    my_hostname = socket.gethostname()

    # Trouver le rapport du pair
    peer_reports = sorted(shared.glob("diagnose-*.json"))
    peer_report = None
    for r in peer_reports:
        if my_hostname not in r.name:
            peer_report = r
            break

    if not peer_report:
        return {"compared": False, "message": "Aucun rapport pair trouvé dans shared/"}

    try:
        peer = json.loads(peer_report.read_text())
    except Exception as e:
        return {"compared": False, "message": f"Erreur lecture rapport pair: {e}"}

    my = run_all_checks(quick=False, check_peer=False)

    diffs = []

    # Comparer les points critiques
    peer_mnemo = peer.get("checks", {}).get("mnemosyne", {})
    my_mnemo = my.get("checks", {}).get("mnemosyne", {})

    if peer_mnemo.get("ok") and not my_mnemo.get("ok"):
        diffs.append("⚠️  LE PAIR a Mnemosyne, PAS NOUS — installer Mnemosyne")
    if my_mnemo.get("ok") and not peer_mnemo.get("ok"):
        diffs.append("⚠️  NOUS avons Mnemosyne, PAS LE PAIR — le pair doit installer Mnemosyne")

    peer_wm = peer_mnemo.get("details", {}).get("working_memories", 0)
    my_wm = my_mnemo.get("details", {}).get("working_memories", 0)
    if isinstance(peer_wm, int) and isinstance(my_wm, int):
        ratio = my_wm / max(peer_wm, 1)
        if ratio < 0.1:
            diffs.append(f"⚠️  Écart mémoire important: nous={my_wm}, pair={peer_wm} — bootstrap recommandé")
        elif ratio > 10:
            diffs.append(f"ℹ️  Nous avons plus de mémoires: nous={my_wm}, pair={peer_wm}")

    # Skills
    peer_skills = peer.get("checks", {}).get("hermes", {}).get("details", {}).get("skill_count", 0)
    my_skills = my.get("checks", {}).get("hermes", {}).get("details", {}).get("skill_count", 0)
    if isinstance(peer_skills, int) and isinstance(my_skills, int):
        if abs(peer_skills - my_skills) > 5:
            diffs.append(f"ℹ️  Écart skills: nous={my_skills}, pair={peer_skills} — sync recommandé")

    # Disk space
    peer_disk = peer.get("checks", {}).get("environment", {}).get("details", {}).get("disk_home_free_gb", 0)
    my_disk = my.get("checks", {}).get("environment", {}).get("details", {}).get("disk_home_free_gb", 0)
    if isinstance(peer_disk, (int, float)) and peer_disk < 1:
        diffs.append(f"⚠️  PAIR espace disque critique: {peer_disk} GB")

    return {
        "compared": True,
        "peer_hostname": peer.get("hostname", "?"),
        "peer_timestamp": peer.get("timestamp", "?"),
        "diffs": diffs if diffs else ["✅ Configurations compatibles"],
        "peer_summary": {
            "mnemosyne_ok": peer_mnemo.get("ok"),
            "working_memories": peer_wm,
            "skill_count": peer_skills,
            "disk_free_gb": peer_disk,
        },
    }


# ── Report ──────────────────────────────────────────────────────────

def save_report(checks: dict, shared_dir: str):
    """Sauvegarde le rapport dans shared/ pour le pair."""
    shared = Path(shared_dir)
    if not shared.exists():
        return

    hostname = socket.gethostname()
    report_path = shared / f"diagnose-{hostname}.json"

    report = {
        "hostname": hostname,
        "timestamp": now_iso(),
        "overall_ok": checks.get("overall_ok", False),
        "checks": {
            k: {"ok": v.get("ok"), "issues": v.get("issues", []), "details": v.get("details", {})}
            for k, v in checks.items()
            if k not in ("overall_ok", "peer_comparison")
        },
    }

    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    return report_path


# ── Main ────────────────────────────────────────────────────────────

def run_all_checks(quick: bool = False, check_peer: bool = True) -> dict:
    """Lance tous les checks et retourne le diagnostic complet."""
    checks = {}

    checks["environment"] = check_environment()
    checks["hermes"] = check_hermes()
    checks["mnemosyne"] = check_mnemosyne()
    checks["syncthing"] = check_syncthing(quick=quick)
    checks["shared_master"] = check_shared_master()

    overall_ok = all(c["ok"] for c in checks.values())
    checks["overall_ok"] = overall_ok

    if check_peer:
        checks["peer_comparison"] = compare_with_peer(
            str(Path(os.path.expanduser("~/.hermes/shared")))
        )

    return checks


def print_report(checks: dict):
    """Affiche le diagnostic en texte formaté."""
    hostname = checks.get("environment", {}).get("details", {}).get("hostname", "?")

    print(f"\n{'═' * 60}")
    print(f"  🩺 DIAGNOSTIC ROAMING — {hostname}")
    print(f"{'═' * 60}")

    checks_order = [
        ("environment", "🌍 Environnement"),
        ("hermes", "🔷 Hermes"),
        ("mnemosyne", "🧠 Mnemosyne"),
        ("syncthing", "🔄 Syncthing"),
        ("shared_master", "📁 Shared / master.db"),
    ]

    for key, label in checks_order:
        check = checks.get(key, {})
        ok = check.get("ok", False)
        icon = "✅" if ok else "❌"
        print(f"\n  {icon} {label}")

        details = check.get("details", {})
        # Show key details
        key_details = {
            "environment": ["hostname", "python_version", "disk_home_free_gb"],
            "hermes": ["version", "model", "provider", "profiles", "skill_count"],
            "mnemosyne": ["db_exists", "db_size_mb", "working_memories", "vectors"],
            "syncthing": ["shared_exists", "syncthing_active", "syncthing_version"],
            "shared_master": ["master_db_size_mb", "master_working_memories", "write_test"],
        }

        for dk in key_details.get(key, []):
            if dk in details:
                val = details[dk]
                if isinstance(val, float):
                    val = f"{val:.1f}"
                elif isinstance(val, list):
                    val = ", ".join(str(v) for v in val[:5])
                    if len(details[dk]) > 5:
                        val += f" ... (+{len(details[dk]) - 5})"
                print(f"     {dk}: {val}")

        for issue in check.get("issues", []):
            print(f"     ⚠️  {issue}")

    # Peer comparison
    peer = checks.get("peer_comparison", {})
    if peer.get("compared"):
        print(f"\n  🔍 Comparaison avec le pair ({peer.get('peer_hostname', '?')})")
        for diff in peer.get("diffs", []):
            print(f"     {diff}")

    # Summary
    overall = checks.get("overall_ok", False)
    print(f"\n{'─' * 60}")
    if overall:
        print(f"  ✅ Machine PRÊTE pour le roaming")
    else:
        print(f"  ❌ Machine NON PRÊTE — corriger les problèmes ci-dessus")
    print(f"{'─' * 60}\n")


# ── CLI ─────────────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Hermes Roaming Diagnostic")
    parser.add_argument("--json", action="store_true", help="Sortie JSON uniquement")
    parser.add_argument("--quick", action="store_true", help="Check rapide (sans API Syncthing)")
    parser.add_argument("--no-save", action="store_true", help="Ne pas sauvegarder le rapport")
    parser.add_argument("--check-peer", action="store_true", help="Comparer avec le diagnostic du pair")
    args = parser.parse_args()

    checks = run_all_checks(quick=args.quick, check_peer=args.check_peer)

    if args.json:
        print(json.dumps(checks, indent=2, ensure_ascii=False))
    else:
        print_report(checks)

    # Sauvegarder dans shared/
    if not args.no_save:
        shared_dir = os.path.expanduser("~/.hermes/shared")
        report_path = save_report(checks, shared_dir)
        if report_path:
            print(f"📋 Rapport sauvegardé : {report_path}")

    sys.exit(0 if checks.get("overall_ok", False) else 1)


if __name__ == "__main__":
    main()
