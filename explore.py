"""
explore.py  —  Milestone 1 data exploration

Run this to inspect the listings dataset and wardrobe schema before designing
any tools. Output is printed to the terminal.

Usage:
    python explore.py
"""

from utils.data_loader import load_listings, get_example_wardrobe, get_empty_wardrobe

# ── Listings dataset ──────────────────────────────────────────────────────────

listings = load_listings()
print(f"Total listings: {len(listings)}")
print()

# Sample 5 listings
print("=== First 5 listings ===")
for l in listings[:5]:
    print(
        f"  [{l['id']}] {l['title']}"
        f" | ${l['price']} | size: {l['size']}"
        f" | platform: {l['platform']}"
        f" | tags: {l['style_tags']}"
    )
print()

# Unique values for key filter fields
categories = sorted({l["category"] for l in listings})
platforms  = sorted({l["platform"] for l in listings})
conditions = sorted({l["condition"] for l in listings})
print(f"Categories:  {categories}")
print(f"Platforms:   {platforms}")
print(f"Conditions:  {conditions}")
print(f"Price range: ${min(l['price'] for l in listings)} – ${max(l['price'] for l in listings)}")
print()

# ── Wardrobe schema ───────────────────────────────────────────────────────────

example = get_example_wardrobe()
empty   = get_empty_wardrobe()

print(f"=== Example wardrobe ({len(example['items'])} items) ===")
for item in example["items"]:
    print(
        f"  [{item['id']}] {item['name']}"
        f" | {item['category']} | colors: {item['colors']}"
    )
print()

print(f"=== Empty wardrobe ===")
print(f"  items count: {len(empty['items'])}")
print()

# ── Key observations ──────────────────────────────────────────────────────────
print("=== Observations for tool design ===")
print("  - Listings have style_tags (list) — useful for keyword scoring")
print("  - Size field is freeform ('S/M', 'W30 L30', 'One Size') — substring match needed")
print("  - Platform values: depop, thredUp, poshmark — include in fit card naturally")
print("  - Wardrobe items have 'notes' (nullable) — can add styling context to suggest_outfit")
print("  - Empty wardrobe has items=[] — suggest_outfit must handle this case explicitly")
