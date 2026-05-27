#!/usr/bin/env python3
"""LAPTOP: Import desktop skills from shared/data/desktop-skills.json"""
from hermes_roaming import DATA_DIR, import_skills_from, preflight_check
import os

if __name__ == "__main__":
    preflight_check()
    print(import_skills_from(os.path.join(DATA_DIR, "desktop-skills.json")))
