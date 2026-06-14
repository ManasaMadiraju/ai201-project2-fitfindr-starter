"""
tools.py

The three required FitFindr tools. Each tool is a standalone function that
can be called and tested independently before being wired into the agent loop.

Complete and test each tool before moving to agent.py.

Tools:
    search_listings(description, size, max_price)  → list[dict]
    suggest_outfit(new_item, wardrobe)              → str
    create_fit_card(outfit, new_item)               → str
"""

import os
import re

from dotenv import load_dotenv
from groq import Groq

from utils.data_loader import load_listings

load_dotenv()


# ── Groq client ───────────────────────────────────────────────────────────────

def _get_groq_client():
    """Initialize and return a Groq client using GROQ_API_KEY from .env."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY not set. Add it to a .env file in the project root."
        )
    return Groq(api_key=api_key)


# ── Tool 1: search_listings ───────────────────────────────────────────────────

def search_listings(
    description: str,
    size: str | None = None,
    max_price: float | None = None,
) -> list[dict]:
    """
    Search the mock listings dataset for items matching the description,
    optional size, and optional price ceiling.

    Args:
        description: Keywords describing what the user is looking for
                     (e.g., "vintage graphic tee").
        size:        Size string to filter by, or None to skip size filtering.
                     Matching is case-insensitive substring (e.g., "M" matches "S/M").
        max_price:   Maximum price (inclusive), or None to skip price filtering.

    Returns:
        A list of matching listing dicts, sorted by relevance (best match first).
        Returns an empty list if nothing matches — does NOT raise an exception.

    Each listing dict has the following fields:
        id, title, description, category, style_tags (list), size,
        condition, price (float), colors (list), brand, platform
    """
    listings = load_listings()

    # Filter by max_price
    if max_price is not None:
        listings = [l for l in listings if l["price"] <= max_price]

    # Filter by size — case-insensitive substring match
    if size is not None:
        size_lower = size.lower()
        listings = [l for l in listings if size_lower in l["size"].lower()]

    # Build keyword set from description
    keywords = set(re.findall(r"\b\w+\b", description.lower()))
    # Remove very common words that would match everything
    noise = {"i", "a", "an", "the", "for", "in", "on", "at", "to", "and", "or",
              "is", "it", "im", "me", "my", "what", "how", "looking", "find",
              "want", "need", "some", "out", "there", "s", "re", "style"}
    keywords -= noise

    def _score(listing: dict) -> int:
        """Count keyword matches across all searchable text fields."""
        text_parts = [
            listing["title"],
            listing["description"],
            listing["category"],
            " ".join(listing.get("style_tags", [])),
            " ".join(listing.get("colors", [])),
            listing.get("brand") or "",
        ]
        text = " ".join(text_parts).lower()
        tokens = set(re.findall(r"\b\w+\b", text))
        return len(keywords & tokens)

    scored = [(_score(l), l) for l in listings]
    # Drop listings with no keyword overlap
    scored = [(s, l) for s, l in scored if s > 0]
    scored.sort(key=lambda x: x[0], reverse=True)

    return [l for _, l in scored]


# ── Tool 2: suggest_outfit ────────────────────────────────────────────────────

def suggest_outfit(new_item: dict, wardrobe: dict) -> str:
    """
    Given a thrifted item and the user's wardrobe, suggest 1–2 complete outfits.

    Args:
        new_item: A listing dict (the item the user is considering buying).
        wardrobe: A wardrobe dict with an 'items' key containing a list of
                  wardrobe item dicts. May be empty — handle this gracefully.

    Returns:
        A non-empty string with outfit suggestions.
        If the wardrobe is empty, offers general styling advice for the item
        rather than raising an exception or returning an empty string.
    """
    try:
        client = _get_groq_client()

        item_summary = (
            f"Title: {new_item['title']}\n"
            f"Description: {new_item['description']}\n"
            f"Category: {new_item['category']}\n"
            f"Style tags: {', '.join(new_item.get('style_tags', []))}\n"
            f"Colors: {', '.join(new_item.get('colors', []))}\n"
            f"Condition: {new_item.get('condition', 'unknown')}"
        )

        wardrobe_items = wardrobe.get("items", [])

        if not wardrobe_items:
            # Empty wardrobe — give general styling advice
            prompt = (
                "You're a thrift fashion stylist. A user is considering buying this item:\n\n"
                f"{item_summary}\n\n"
                "Since you don't know their wardrobe yet, give them general styling advice: "
                "what kinds of basics pair well with this piece, what aesthetic or vibe it suits, "
                "and 1–2 complete outfit ideas using common wardrobe staples anyone might own. "
                "Be specific and conversational — name actual piece types (e.g., 'wide-leg jeans', "
                "'white ribbed tank', 'chunky sneakers'). Keep it to 3–5 sentences."
            )
        else:
            # Wardrobe has items — suggest pairings using named pieces
            wardrobe_lines = "\n".join(
                f"- {item['name']} ({item['category']}, {', '.join(item.get('colors', []))})"
                + (f" — {item['notes']}" if item.get("notes") else "")
                for item in wardrobe_items
            )
            prompt = (
                "You're a thrift fashion stylist. A user is considering buying this item:\n\n"
                f"{item_summary}\n\n"
                "Their current wardrobe includes:\n"
                f"{wardrobe_lines}\n\n"
                "Suggest 1–2 specific outfit combinations using the new item paired with "
                "named pieces from their wardrobe. Call out the exact wardrobe items by name, "
                "describe the overall look and vibe, and add any small styling tips "
                "(e.g., tucking, layering, rolling sleeves). Keep it conversational and specific — "
                "3–6 sentences total."
            )

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
        )
        result = response.choices[0].message.content.strip()
        return result if result else _suggest_outfit_fallback(new_item)

    except Exception:
        return _suggest_outfit_fallback(new_item)


def _suggest_outfit_fallback(new_item: dict) -> str:
    category = new_item.get("category", "piece")
    tags = new_item.get("style_tags", [])
    vibe = tags[0] if tags else "versatile"
    return (
        f"Unable to generate outfit suggestions right now. "
        f"This {category} has a {vibe} vibe — consider pairing it with "
        f"complementary basics like neutral bottoms, classic sneakers, or a simple layer."
    )


# ── Tool 3: create_fit_card ───────────────────────────────────────────────────

def create_fit_card(outfit: str, new_item: dict) -> str:
    """
    Generate a short, shareable outfit caption for the thrifted find.

    Args:
        outfit:   The outfit suggestion string from suggest_outfit().
        new_item: The listing dict for the thrifted item.

    Returns:
        A 2–4 sentence string usable as an Instagram/TikTok caption.
        If outfit is empty or missing, return a descriptive error message
        string — do NOT raise an exception.

    The caption:
    - Feels casual and authentic (like a real OOTD post, not a product description)
    - Mentions the item name, price, and platform naturally (once each)
    - Captures the outfit vibe in specific terms
    - Sounds different each time for different inputs (temperature=1.2)
    """
    if not outfit or not outfit.strip():
        return (
            "Cannot generate a fit card without an outfit suggestion. "
            "Please try your search again."
        )

    try:
        client = _get_groq_client()

        title = new_item.get("title", "this piece")
        price = new_item.get("price", 0)
        platform = new_item.get("platform", "a thrift app")

        prompt = (
            f"Write a casual, authentic Instagram/TikTok OOTD caption (2–4 sentences) "
            f"for this outfit.\n\n"
            f"Thrifted item: {title} — ${price:.0f} on {platform}\n"
            f"Outfit: {outfit}\n\n"
            "Rules:\n"
            "- Sound like a real person posting their outfit, NOT a product description\n"
            "- Mention the item name, price, and platform naturally — each exactly once\n"
            "- Capture the specific vibe of the outfit (e.g., 'full 90s grunge', 'quiet luxury', "
            "'clean streetwear')\n"
            "- Use lowercase casual language; 1–2 relevant emojis are fine\n"
            "- Do NOT start the caption with the word 'Just' or 'Found'\n"
            "- Write ONLY the caption text, nothing else — no quotes, no labels"
        )

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=1.2,
        )
        result = response.choices[0].message.content.strip()
        return result if result else "Fit card unavailable — check your API key and try again."

    except Exception:
        return "Fit card unavailable — check your API key and try again."
