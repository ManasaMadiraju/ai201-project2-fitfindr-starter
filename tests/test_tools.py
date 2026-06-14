"""
tests/test_tools.py

Pytest tests for FitFindr tools — one test per failure mode plus happy-path
coverage. Run with:
    pytest tests/
"""

import pytest
from tools import search_listings, suggest_outfit, create_fit_card
from utils.data_loader import get_example_wardrobe, get_empty_wardrobe


# ── search_listings ───────────────────────────────────────────────────────────

def test_search_returns_results():
    """Happy path — common query should return at least one result."""
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert isinstance(results, list)
    assert len(results) > 0


def test_search_result_structure():
    """Each result should be a dict with all required listing fields."""
    results = search_listings("vintage jacket", size=None, max_price=100)
    assert len(results) > 0
    required_fields = {"id", "title", "description", "category", "style_tags",
                       "size", "condition", "price", "colors", "platform"}
    for item in results:
        assert required_fields.issubset(item.keys()), f"Missing fields in: {item}"


def test_search_empty_results():
    """Impossible query should return [] without raising an exception."""
    results = search_listings("designer ballgown", size="XXS", max_price=5)
    assert results == []


def test_search_price_filter():
    """All returned items must have price <= max_price."""
    results = search_listings("vintage tee", size=None, max_price=25)
    assert len(results) > 0
    assert all(item["price"] <= 25 for item in results)


def test_search_price_filter_excludes_over_budget():
    """Items over max_price should never appear in results."""
    results = search_listings("vintage", size=None, max_price=10)
    # The listings dataset has items priced $12+, so this may return []
    # but it must not include anything over $10
    assert all(item["price"] <= 10 for item in results)


def test_search_size_filter():
    """Results should only include listings whose size field contains the given size."""
    results = search_listings("top", size="M", max_price=None)
    for item in results:
        assert "m" in item["size"].lower(), (
            f"Size filter failed: '{item['size']}' does not contain 'M'"
        )


def test_search_no_size_filter_returns_more():
    """Removing size filter should return >= as many results."""
    with_size = search_listings("vintage", size="M", max_price=None)
    without_size = search_listings("vintage", size=None, max_price=None)
    assert len(without_size) >= len(with_size)


def test_search_relevance_ordering():
    """Best keyword match should appear first."""
    results = search_listings("graphic tee", size=None, max_price=None)
    assert len(results) > 0
    # The top result's combined text should contain at least one of our keywords
    top = results[0]
    combined = (top["title"] + " " + " ".join(top["style_tags"])).lower()
    assert "graphic" in combined or "tee" in combined


# ── suggest_outfit ────────────────────────────────────────────────────────────

def test_suggest_outfit_with_example_wardrobe():
    """Happy path — should return a non-empty string with wardrobe items."""
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert len(results) > 0
    suggestion = suggest_outfit(results[0], get_example_wardrobe())
    assert isinstance(suggestion, str)
    assert len(suggestion.strip()) > 0


def test_suggest_outfit_empty_wardrobe():
    """Empty wardrobe should return general styling advice, not raise or return ''."""
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert len(results) > 0
    suggestion = suggest_outfit(results[0], get_empty_wardrobe())
    assert isinstance(suggestion, str)
    assert len(suggestion.strip()) > 0


def test_suggest_outfit_empty_wardrobe_no_exception():
    """Tool must not raise any exception when wardrobe items list is empty."""
    item = {
        "id": "test_001",
        "title": "Test Tee",
        "description": "A test tee",
        "category": "tops",
        "style_tags": ["vintage"],
        "size": "M",
        "condition": "good",
        "price": 20.0,
        "colors": ["black"],
        "brand": None,
        "platform": "depop",
    }
    result = suggest_outfit(item, {"items": []})
    # Should return a string, not raise
    assert isinstance(result, str)


# ── create_fit_card ───────────────────────────────────────────────────────────

def test_create_fit_card_empty_outfit_returns_error_string():
    """Empty outfit string should return an error message string, not raise."""
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert len(results) > 0
    result = create_fit_card("", results[0])
    assert isinstance(result, str)
    assert len(result) > 0
    # Should communicate the problem, not return silently
    assert any(word in result.lower() for word in ("cannot", "error", "without", "unavailable"))


def test_create_fit_card_whitespace_outfit_returns_error_string():
    """Whitespace-only outfit string should also return an error, not raise."""
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert len(results) > 0
    result = create_fit_card("   \n  ", results[0])
    assert isinstance(result, str)
    assert any(word in result.lower() for word in ("cannot", "error", "without", "unavailable"))


def test_create_fit_card_valid_input():
    """Valid outfit input should return a non-empty caption string."""
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert len(results) > 0
    outfit = "Pair with wide-leg jeans and chunky white sneakers for a 90s streetwear look."
    result = create_fit_card(outfit, results[0])
    assert isinstance(result, str)
    assert len(result.strip()) > 20


def test_create_fit_card_no_exception_on_any_input():
    """Tool must never raise — it always returns a string."""
    item = {
        "id": "test_001",
        "title": "Test Jacket",
        "description": "A test jacket",
        "category": "outerwear",
        "style_tags": ["vintage"],
        "size": "M",
        "condition": "good",
        "price": 35.0,
        "colors": ["black"],
        "brand": None,
        "platform": "depop",
    }
    # Should not raise even with minimal item data
    result = create_fit_card("Layer over a white tank with black boots.", item)
    assert isinstance(result, str)
