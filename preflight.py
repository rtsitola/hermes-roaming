"""
Hermes Roaming — Pre-flight Check
==================================

Check minimal avant toute opération de sync.
Importé par les scripts import-*.py.

Usage:
    from preflight import check_ready, MINIMUM_REQUIREMENTS

    issues = check_ready()
    if issues:
        for i in issues:
            print(f"❌ {i}")
        sys.exit(1)
"""

import os
import sqlite3
from pathlib import Path


MINIMUM_REQUIREMENTS = {
    "mnemosyne_db": "~/.hermes/mnemosyne/data/mnemosyne.db",
    "shared_dir": "~/.hermes/shared",
    "master_db": "~/.hermes/shared/master.db",
    "hermes_config": "~/.hermes/config.yaml",
}


def check_ready() -> list[str]:
    """
    Vérifie les prérequis minimum pour le roaming.
    Returns: liste de problèmes (vide = OK).
    """
    issues = []

    for name, path_str in MINIMUM_REQUIREMENTS.items():
        path = Path(os.path.expanduser(path_str))
        if not path.exists():
            issues.append(f"{name} absent: {path_str}")
            continue

        # Vérifications spécifiques
        if name == "mnemosyne_db":
            try:
                conn = sqlite3.connect(str(path))
                count = conn.execute("SELECT COUNT(*) FROM working_memory").fetchone()[0]
                conn.close()
                if count == 0:
                    issues.append(f"Mnemosyne vide (0 working memories) — bootstrap nécessaire")
            except sqlite3.OperationalError as e:
                issues.append(f"Mnemosyne corrompu: {e}")
            except Exception as e:
                issues.append(f"Mnemosyne inaccessible: {e}")

        if name == "master_db":
            try:
                conn = sqlite3.connect(str(path))
                conn.execute("SELECT COUNT(*) FROM working_memory").fetchone()
                conn.close()
            except sqlite3.OperationalError as e:
                issues.append(f"master.db corrompu ou schéma incompatible: {e}")
            except Exception as e:
                issues.append(f"master.db inaccessible: {e}")

    # Vérifier l'espace disque
    try:
        import shutil
        home_usage = shutil.disk_usage(os.path.expanduser("~"))
        if home_usage.free < 100 * 1024 * 1024:  # 100 MB
            issues.append(f"Espace disque critique: {round(home_usage.free / (1024**3), 1)} GB libres")
    except Exception:
        pass

    return issues


def check_peer_diagnostic() -> dict:
    """
    Lit le diagnostic du pair depuis shared/.
    Returns: dict avec les problèmes détectés, ou {} si tout OK.
    """
    shared = Path(os.path.expanduser("~/.hermes/shared"))
    import socket
    my_hostname = socket.gethostname()

    peer_reports = sorted(shared.glob("diagnose-*.json"))
    for report in peer_reports:
        if my_hostname not in report.name:
            # C'est le rapport du pair
            import json
            try:
                data = json.loads(report.read_text())
            except Exception:
                return {"error": f"Rapport pair illisible: {report.name}"}

            issues = []

            # Check Mnemosyne
            mnemo = data.get("checks", {}).get("mnemosyne", {})
            if not mnemo.get("ok"):
                issues.append(f"LE PAIR n'a PAS Mnemosyne — sync mémoire impossible")

            # Check shared access
            shared_check = data.get("checks", {}).get("shared_master", {})
            if not shared_check.get("ok"):
                issues.append("Le pair n'a pas accès à master.db")

            if issues:
                return {"peer": report.name.replace("diagnose-", "").replace(".json", ""),
                        "issues": issues}
            return {}

    return {"error": "Aucun rapport pair trouvé"}


if __name__ == "__main__":
    issues = check_ready()
    if issues:
        print("❌ Prérequis manquants :")
        for i in issues:
            print(f"   {i}")
        exit(1)
    else:
        print("✅ Prérequis OK")
        peer = check_peer_diagnostic()
        if peer and peer.get("issues"):
            print(f"⚠️  Problèmes détectés chez le pair ({peer.get('peer', '?')}):")
            for i in peer["issues"]:
                print(f"   {i}")
