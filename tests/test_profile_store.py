# tests/test_profile_store.py
import json
import os
import pytest
from unittest.mock import patch
from reddit_toolkit.profile_store import (
    load, save, list_profiles, new_profile, slugify, ProfileNotFoundError
)


def test_slugify():
    assert slugify("My Cool App") == "my-cool-app"
    assert slugify("  Reddit Tool! ") == "reddit-tool"


def test_save_and_load(tmp_path):
    with patch.dict(os.environ, {"REDDIT_TOOLKIT_DATA_DIR": str(tmp_path)}):
        profile = new_profile("Test App")
        save(profile)
        loaded = load("test-app")
    assert loaded["name"] == "Test App"
    assert loaded["id"] == "test-app"


def test_load_missing_raises(tmp_path):
    with patch.dict(os.environ, {"REDDIT_TOOLKIT_DATA_DIR": str(tmp_path)}):
        with pytest.raises(ProfileNotFoundError):
            load("nonexistent")


def test_list_profiles(tmp_path):
    with patch.dict(os.environ, {"REDDIT_TOOLKIT_DATA_DIR": str(tmp_path)}):
        save(new_profile("App One"))
        save(new_profile("App Two"))
        profiles = list_profiles()
    assert len(profiles) == 2
    names = {p["name"] for p in profiles}
    assert names == {"App One", "App Two"}
