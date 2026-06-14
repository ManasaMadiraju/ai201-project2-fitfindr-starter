"""
memory.py

Style profile memory — saves and loads a user's wardrobe across sessions.
Profiles are stored as JSON in data/style_profile.json.

Functions:
    save_style_profile(wardrobe)  → str    (success / error message)
    load_style_profile()          → dict | None
    profile_exists()              → bool
"""

import json
import os
from datetime import datetime

_PROFILE_PATH = os.path.join(os.path.dirname(__file__), "data", "style_profile.json")


def save_style_profile(wardrobe: dict, filepath: str = _PROFILE_PATH) -> str:
    """
    Save a wardrobe dict to disk for use in future sessions.

    Args:
        wardrobe: Wardrobe dict with an 'items' key (list of wardrobe item dicts).
        filepath: Where to write the JSON file (default: data/style_profile.json).

    Returns:
        A success message string on save, or a descriptive error string on failure.
        Never raises.
    """
    try:
        profile = {
            "wardrobe": wardrobe,
            "saved_at": datetime.now().isoformat(),
        }
        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(profile, f, indent=2)
        count = len(wardrobe.get("items", []))
        return f"Style profile saved! {count} wardrobe item(s) will be remembered next time."
    except Exception as e:
        return f"Could not save profile: {e}"


def load_style_profile(filepath: str = _PROFILE_PATH) -> dict | None:
    """
    Load a saved wardrobe from disk.

    Args:
        filepath: Path to the profile JSON file.

    Returns:
        The wardrobe dict (with 'items' key) if a valid profile exists,
        or None if the file is missing or unreadable.
    """
    try:
        if not os.path.exists(filepath):
            return None
        with open(filepath, "r", encoding="utf-8") as f:
            profile = json.load(f)
        wardrobe = profile.get("wardrobe")
        # Validate minimal structure
        if isinstance(wardrobe, dict) and "items" in wardrobe:
            return wardrobe
        return None
    except Exception:
        return None


def profile_exists(filepath: str = _PROFILE_PATH) -> bool:
    """Return True if a saved profile file exists on disk."""
    return os.path.exists(filepath)


def profile_saved_at(filepath: str = _PROFILE_PATH) -> str | None:
    """Return the ISO timestamp string of when the profile was last saved, or None."""
    try:
        if not os.path.exists(filepath):
            return None
        with open(filepath, "r", encoding="utf-8") as f:
            profile = json.load(f)
        return profile.get("saved_at")
    except Exception:
        return None
