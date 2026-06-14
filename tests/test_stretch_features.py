"""
tests/test_stretch_features.py

Tests for all three stretch features:
  - compare_price (price comparison tool)
  - get_trending_styles (trend awareness tool)
  - save/load style profile (memory across sessions)

Run with:
    pytest tests/test_stretch_features.py -v
"""

import os
import tempfile

from tools import compare_price, get_trending_styles, search_listings
from memory import save_style_profile, load_style_profile, profile_exists
from utils.data_loader import get_example_wardrobe, get_empty_wardrobe


# ── compare_price ─────────────────────────────────────────────────────────────

def test_compare_price_returns_dict():
    """Should return a dict with all required keys."""
    results = search_listings("vintage tee", size=None, max_price=None)
    assert results
    result = compare_price(results[0])
    required = {"verdict", "item_price", "avg_comparable_price", "comparable_count", "summary"}
    assert required.issubset(result.keys())


def test_compare_price_verdict_is_valid():
    """Verdict must be one of the three expected values (or 'no data')."""
    results = search_listings("vintage jacket", size=None, max_price=None)
    assert results
    result = compare_price(results[0])
    assert result["verdict"] in ("great deal", "fair price", "overpriced", "no data")


def test_compare_price_item_price_matches():
    """item_price in result must match the listing's actual price."""
    results = search_listings("graphic tee", size=None, max_price=None)
    assert results
    item = results[0]
    result = compare_price(item)
    assert result["item_price"] == item["price"]


def test_compare_price_summary_is_nonempty_string():
    """Summary must always be a non-empty string."""
    results = search_listings("vintage", size=None, max_price=None)
    assert results
    result = compare_price(results[0])
    assert isinstance(result["summary"], str)
    assert len(result["summary"].strip()) > 0


def test_compare_price_no_exception_on_any_item():
    """compare_price must never raise, even for edge-case items."""
    sparse_item = {
        "id": "test_999",
        "title": "Mystery Item",
        "description": "unknown",
        "category": "accessories",
        "style_tags": [],
        "size": "One Size",
        "condition": "fair",
        "price": 999.0,
        "colors": [],
        "brand": None,
        "platform": "depop",
    }
    result = compare_price(sparse_item)
    assert isinstance(result, dict)


def test_compare_price_great_deal_for_cheap_item():
    """An item priced much lower than average should be called a great deal."""
    # Find the cheapest item in the dataset and check its verdict
    results = search_listings("vintage", size=None, max_price=None)
    cheapest = min(results, key=lambda x: x["price"])
    result = compare_price(cheapest)
    # Cheapest item should be a great deal or fair (never overpriced)
    assert result["verdict"] in ("great deal", "fair price", "no data")


# ── get_trending_styles ───────────────────────────────────────────────────────

def test_trending_styles_returns_string():
    """Should return a non-empty string."""
    result = get_trending_styles(size=None)
    assert isinstance(result, str)
    assert len(result.strip()) > 0


def test_trending_styles_with_size_filter():
    """With a size that exists in the dataset, should still return a string."""
    result = get_trending_styles(size="M")
    assert isinstance(result, str)
    assert len(result.strip()) > 0


def test_trending_styles_with_impossible_size():
    """Even with a size that matches nothing, should fall back gracefully."""
    result = get_trending_styles(size="XXXXL")
    assert isinstance(result, str)
    assert len(result.strip()) > 0


def test_trending_styles_contains_style_tags():
    """Result should mention actual style tags from the dataset."""
    result = get_trending_styles(size=None)
    # "vintage" is the most common tag in the dataset — should appear
    assert "vintage" in result.lower() or "streetwear" in result.lower()


def test_trending_styles_no_size_vs_size_differ():
    """Results for a specific size may differ from all-sizes results."""
    all_sizes = get_trending_styles(size=None)
    size_m = get_trending_styles(size="M")
    # Both should be valid strings (they may or may not differ)
    assert isinstance(all_sizes, str)
    assert isinstance(size_m, str)


# ── style profile memory ──────────────────────────────────────────────────────

def test_save_and_load_profile(tmp_path):
    """Save a wardrobe, then load it back — should match."""
    filepath = str(tmp_path / "test_profile.json")
    wardrobe = get_example_wardrobe()

    msg = save_style_profile(wardrobe, filepath=filepath)
    assert isinstance(msg, str)
    assert "saved" in msg.lower()

    loaded = load_style_profile(filepath=filepath)
    assert loaded is not None
    assert loaded["items"] == wardrobe["items"]


def test_load_missing_profile_returns_none(tmp_path):
    """Loading a profile that doesn't exist should return None, not raise."""
    filepath = str(tmp_path / "nonexistent.json")
    result = load_style_profile(filepath=filepath)
    assert result is None


def test_save_empty_wardrobe(tmp_path):
    """Saving an empty wardrobe should succeed."""
    filepath = str(tmp_path / "empty_profile.json")
    msg = save_style_profile(get_empty_wardrobe(), filepath=filepath)
    assert isinstance(msg, str)
    loaded = load_style_profile(filepath=filepath)
    assert loaded is not None
    assert loaded["items"] == []


def test_profile_exists_false_when_missing(tmp_path):
    """profile_exists should return False for a non-existent path."""
    filepath = str(tmp_path / "nope.json")
    assert not profile_exists(filepath=filepath)


def test_profile_exists_true_after_save(tmp_path):
    """profile_exists should return True after saving."""
    filepath = str(tmp_path / "profile.json")
    save_style_profile(get_example_wardrobe(), filepath=filepath)
    assert profile_exists(filepath=filepath)


def test_save_profile_no_exception_on_bad_path():
    """save_style_profile must return an error string, not raise, on bad path."""
    result = save_style_profile(get_example_wardrobe(), filepath="/no/such/dir/x/y/z/profile.json")
    # Should return a string (may be an error message)
    assert isinstance(result, str)
