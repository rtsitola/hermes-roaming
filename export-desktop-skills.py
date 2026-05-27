#!/usr/bin/env python3
"""Export desktop skills to shared/data/desktop-skills.json"""
from hermes_roaming import DATA_DIR, export_skills_to
import os

if __name__ == "__main__":
    print(export_skills_to(os.path.join(DATA_DIR, "desktop-skills.json")))
