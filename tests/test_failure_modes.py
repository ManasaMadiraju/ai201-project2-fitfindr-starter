"""
tests/test_failure_modes.py  —  Milestone 5 deliberate failure triggers

These tests deliberately invoke each tool's known failure mode and verify the
agent responds gracefully — no uncaught exceptions, no silent empty returns.

Run with:
    pytest tests/test_failure_modes.py -v
"""

from tools import search_listings, suggest_outfit, create_fit_card
from utils.data_loader import get_example_wardrobe, get_empty_wardrobe
from agent import run_agent


# ── Failure mode 1: search_listings returns no results ────────────────────────

def test_search_impossible_query_returns_empty_list():
    """
    Milestone 5, Step 1 — trigger search_listings with zero matches.
    Must return [] without raising.
    """
    results = search_listings("designer ballgown", size="XXS", max_price=5)
    assert results == [], f"Expected [], got {results}"


def test_agent_no_results_sets_error_not_fit_card():
    """
    When search returns nothing, agent must set session['error'] and leave
    fit_card as None — it must NOT call suggest_outfit with empty input.
    """
    session = run_agent("designer ballgown size XXS under $5", get_example_wardrobe())
    assert session["error"] is not None, "Expected an error message"
    assert session["fit_card"] is None, "fit_card should be None on early exit"
    assert session["outfit_suggestion"] is None, "outfit_suggestion should be None on early exit"


def test_agent_error_message_is_actionable():
    """Error message should tell the user what to try next, not just 'no results'."""
    session = run_agent("designer ballgown size XXS under $5", get_example_wardrobe())
    msg = session["error"].lower()
    # Should mention what was searched and give a hint
    assert any(word in msg for word in ("try", "keyword", "price", "size", "filter")), (
        f"Error message is not actionable: {session['error']}"
    )


# ── Failure mode 2: suggest_outfit with empty wardrobe ───────────────────────

def test_suggest_outfit_empty_wardrobe_no_exception():
    """
    Milestone 5, Step 2 — trigger suggest_outfit with get_empty_wardrobe().
    Must return a non-empty string, never raise.
    """
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert results, "Need at least one result to test suggest_outfit"
    result = suggest_outfit(results[0], get_empty_wardrobe())
    assert isinstance(result, str), "suggest_outfit must return a string"
    assert result.strip(), "suggest_outfit must not return an empty string for empty wardrobe"


def test_suggest_outfit_empty_wardrobe_returns_useful_advice():
    """General styling advice should mention piece types or aesthetics, not be a one-liner."""
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    result = suggest_outfit(results[0], get_empty_wardrobe())
    assert len(result) > 50, f"Response too short to be useful: {result!r}"


# ── Failure mode 3: create_fit_card with empty outfit string ─────────────────

def test_create_fit_card_empty_string_no_exception():
    """
    Milestone 5, Step 3 — trigger create_fit_card with outfit=''.
    Must return a descriptive error string, never raise.
    """
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert results, "Need at least one result to test create_fit_card"
    result = create_fit_card("", results[0])
    assert isinstance(result, str), "create_fit_card must return a string"
    assert result.strip(), "create_fit_card must not return an empty string"
    assert any(word in result.lower() for word in ("cannot", "error", "without", "unavailable")), (
        f"Error string not descriptive enough: {result!r}"
    )


def test_create_fit_card_whitespace_only_no_exception():
    """Whitespace-only outfit string should also be caught by the guard."""
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    result = create_fit_card("   \n\t  ", results[0])
    assert isinstance(result, str)
    assert any(word in result.lower() for word in ("cannot", "error", "without", "unavailable"))


# ── Stretch: retry with loosened size filter ──────────────────────────────────

def test_agent_retry_loosens_size_filter():
    """
    When a size-filtered query returns nothing but a size-free query would
    find results, the agent should retry and set retry_note.
    """
    # "vintage" items exist, but none are size "XXS"
    session = run_agent("vintage tee size XXS", get_example_wardrobe())
    if session["error"] is None:
        # Agent succeeded via retry — retry_note should explain the relaxation
        assert session["retry_note"] is not None, (
            "Agent found results via retry but did not set retry_note"
        )
        assert "size" in session["retry_note"].lower()
