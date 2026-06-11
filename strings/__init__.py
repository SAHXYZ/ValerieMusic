# strings/__init__.py
import os
import yaml
from typing import Dict

languages: Dict[str, dict] = {}
languages_present: Dict[str, str] = {}

BASE_DIR = os.path.dirname(__file__)
LANGS_DIR = os.path.join(BASE_DIR, "langs")


def get_string(lang: str):
    """
    Safely return language dict. Fallback to English if missing.
    """
    if lang in languages:
        return languages[lang]
    return languages.get("en", {})


def _load_languages():
    """
    Load languages from absolute path.
    Fixes old CWD bug on Heroku/VPS.
    """
    if not os.path.isdir(LANGS_DIR):
        print(f"[strings] langs directory not found: {LANGS_DIR}")
        return

    yml_files = sorted([
        f for f in os.listdir(LANGS_DIR)
        if f.endswith((".yml", ".yaml"))
    ])

    # Load English first
    en_file = None
    for name in ("en.yml", "en.yaml"):
        if name in yml_files:
            en_file = name
            break

    if en_file:
        en_path = os.path.join(LANGS_DIR, en_file)
        try:
            languages["en"] = yaml.safe_load(open(en_path, encoding="utf8")) or {}
            languages_present["en"] = languages["en"].get("name", "English")
        except Exception as e:
            print(f"[strings] Failed to load {en_path}: {e}")
            languages["en"] = {}
    else:
        print("[strings] WARNING: en.yml not found!")

    # Load remaining languages
    for filename in yml_files:
        language_name = filename[:-4]
        if language_name == "en":
            continue

        path = os.path.join(LANGS_DIR, filename)
        try:
            lang_map = yaml.safe_load(open(path, encoding="utf8")) or {}
        except Exception as e:
            print(f"[strings] Failed to load {path}: {e}")
            continue

        # Merge missing keys from English
        if "en" in languages:
            for k in languages["en"]:
                if k not in lang_map:
                    lang_map[k] = languages["en"][k]

        languages[language_name] = lang_map
        languages_present[language_name] = lang_map.get("name", language_name)


# Load language files on import
_load_languages()
