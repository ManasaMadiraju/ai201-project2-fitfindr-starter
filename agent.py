"""
agent.py

The FitFindr planning loop. Orchestrates the three tools in response to a
natural language user query, passing state between them via a session dict.

Complete tools.py and test each tool in isolation before implementing this file.

Usage (once implemented):
    from agent import run_agent
    from utils.data_loader import get_example_wardrobe

    result = run_agent(
        query="vintage graphic tee under $30, size M",
        wardrobe=get_example_wardrobe(),
    )
    print(result["fit_card"])
    print(result["error"])   # None on success
"""

import re

from tools import search_listings, suggest_outfit, create_fit_card, compare_price, get_trending_styles


# ── session state ─────────────────────────────────────────────────────────────

def _new_session(query: str, wardrobe: dict) -> dict:
    """
    Initialize and return a fresh session dict for one user interaction.

    The session dict is the single source of truth for everything that happens
    during a run — it stores the original query, parsed parameters, tool results,
    and any error that caused early termination.
    """
    return {
        "query": query,              # original user query
        "parsed": {},                # extracted description / size / max_price
        "search_results": [],        # list of matching listing dicts
        "selected_item": None,       # top result, passed into suggest_outfit
        "wardrobe": wardrobe,        # user's wardrobe dict
        "outfit_suggestion": None,   # string returned by suggest_outfit
        "fit_card": None,            # string returned by create_fit_card
        "error": None,               # set if the interaction ended early
        "retry_note": None,          # set if size filter was loosened on retry
        "trending": None,            # string from get_trending_styles
        "price_verdict": None,       # dict from compare_price
    }


# ── query parsing ─────────────────────────────────────────────────────────────

def _parse_query(query: str) -> dict:
    """
    Extract description, size, and max_price from a natural language query.

    Uses regex — no LLM call needed for this step.
    - max_price: matches "$30", "under $30", "under 30", "max $30", "below 30"
    - size: matches "size M" or standalone XS/S/M/L/XL/XXL
    - description: original query with price/size fragments removed
    """
    working = query

    # Extract max_price
    price_pattern = re.compile(
        r"(?:under|max|below|less\s+than)\s+\$?(\d+(?:\.\d+)?)"
        r"|\$(\d+(?:\.\d+)?)",
        re.IGNORECASE,
    )
    price_match = price_pattern.search(working)
    max_price = None
    if price_match:
        raw = price_match.group(1) or price_match.group(2)
        max_price = float(raw)
        working = working[: price_match.start()] + " " + working[price_match.end() :]

    # Extract size — prefer "size M" phrasing, fall back to standalone abbreviation
    size_match = re.search(r"\bsize\s+([A-Za-z0-9/]+)", working, re.IGNORECASE)
    if not size_match:
        size_match = re.search(r"\b(XXS|XS|S/M|SM|S|M|L/XL|XL|XXL)\b", working)
    size = None
    if size_match:
        size = size_match.group(1).upper()
        working = working[: size_match.start()] + " " + working[size_match.end() :]

    # Clean up remaining description
    description = " ".join(working.split()).strip()
    if not description:
        description = query  # fallback to original if everything was extracted

    return {"description": description, "size": size, "max_price": max_price}


# ── planning loop ─────────────────────────────────────────────────────────────

def run_agent(query: str, wardrobe: dict) -> dict:
    """
    Main agent entry point. Runs the FitFindr planning loop for a single
    user interaction and returns the completed session dict.

    Args:
        query:    Natural language user request
                  (e.g., "vintage graphic tee under $30, size M")
        wardrobe: User's wardrobe dict — use get_example_wardrobe() or
                  get_empty_wardrobe() from utils/data_loader.py

    Returns:
        The session dict after the interaction completes. Check session["error"]
        first — if it is not None, the interaction ended early and the other
        output fields (outfit_suggestion, fit_card) will be None.
    """
    # Step 1: Initialize session
    session = _new_session(query, wardrobe)

    # Step 2: Parse the query into structured parameters
    parsed = _parse_query(query)
    session["parsed"] = parsed

    description = parsed["description"]
    size = parsed["size"]
    max_price = parsed["max_price"]

    # Step 3: Get trending styles (always runs — useful even on no-results path)
    session["trending"] = get_trending_styles(size)

    # Step 4: Search listings with parsed parameters
    results = search_listings(description, size, max_price)
    session["search_results"] = results

    # Stretch feature — retry with size filter removed if no results
    if not results and size is not None:
        results = search_listings(description, None, max_price)
        session["search_results"] = results
        if results:
            session["retry_note"] = (
                f"No listings found for size {size} — showing results for all sizes."
            )

    # Early exit if still no results
    if not results:
        parts = [f'"{description}"']
        if size:
            parts.append(f"in size {size}")
        if max_price:
            parts.append(f"under ${max_price:.0f}")
        session["error"] = (
            f"No listings found for {' '.join(parts)}. "
            "Try different keywords, a higher price ceiling, or leave out the size filter."
        )
        return session

    # Step 5: Select the top result
    session["selected_item"] = results[0]

    # Step 6: Compare price against comparable listings
    session["price_verdict"] = compare_price(session["selected_item"])

    # Step 7: Suggest outfit combinations using the selected item and wardrobe
    session["outfit_suggestion"] = suggest_outfit(
        session["selected_item"], wardrobe
    )

    # Step 8: Generate a shareable fit card caption
    session["fit_card"] = create_fit_card(
        session["outfit_suggestion"], session["selected_item"]
    )

    # Step 7: Return the completed session
    return session


# ── CLI test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from utils.data_loader import get_example_wardrobe, get_empty_wardrobe

    print("=== Happy path: graphic tee ===\n")
    session = run_agent(
        query="looking for a vintage graphic tee under $30",
        wardrobe=get_example_wardrobe(),
    )
    if session["error"]:
        print(f"Error: {session['error']}")
    else:
        print(f"Found: {session['selected_item']['title']}")
        if session["retry_note"]:
            print(f"Note: {session['retry_note']}")
        print(f"\nOutfit: {session['outfit_suggestion']}")
        print(f"\nFit card: {session['fit_card']}")

    print("\n\n=== No-results path ===\n")
    session2 = run_agent(
        query="designer ballgown size XXS under $5",
        wardrobe=get_example_wardrobe(),
    )
    print(f"Error message: {session2['error']}")

    print("\n\n=== Empty wardrobe path ===\n")
    session3 = run_agent(
        query="vintage flannel under $30",
        wardrobe=get_empty_wardrobe(),
    )
    if session3["error"]:
        print(f"Error: {session3['error']}")
    else:
        print(f"Found: {session3['selected_item']['title']}")
        print(f"\nOutfit (general advice): {session3['outfit_suggestion']}")
        print(f"\nFit card: {session3['fit_card']}")
