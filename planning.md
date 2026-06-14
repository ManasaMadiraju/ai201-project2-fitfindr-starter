# FitFindr — planning.md

---

## Tools

### Tool 1: search_listings

**What it does:**
Goes through all 40 listings in `data/listings.json` and finds ones that match what you're looking for. First it cuts anything over the price limit or the wrong size. Then it scores what's left by counting how many of your keywords show up in the title, description, category, style tags, colors, and brand. Best matches come back first.

**Input parameters:**
- `description` (str): What you're looking for — e.g. "vintage graphic tee" or "90s track jacket". Used to score listings by keyword overlap.
- `size` (str | None): Like "M" or "S/M". Checks if your size appears anywhere in the listing's size field. Pass None to skip size filtering.
- `max_price` (float | None): Price ceiling in dollars. Listings above this get dropped. Pass None to skip price filtering.

**What it returns:**
A list of listing dicts sorted by best match. Each one has: `id`, `title`, `description`, `category`, `style_tags`, `size`, `condition`, `price`, `colors`, `brand`, `platform`. Returns an empty list if nothing matches — never crashes.

**What happens if it fails or returns nothing:**
The agent checks right away if the list came back empty. If the user gave a size, it retries without the size filter first. If that still finds nothing, the agent sets an error message like: *"No listings found for 'designer ballgown' in size XXS under $5. Try different keywords, a higher price, or leave out the size filter."* — and stops there without calling the other tools.

---

### Tool 2: suggest_outfit

**What it does:**
Takes the item from the search and the user's wardrobe, then asks the Groq LLM to suggest 1–2 outfits. If the wardrobe has items, the response mentions specific pieces by name. If the wardrobe is empty, it gives general styling advice instead of failing.

**Input parameters:**
- `new_item` (dict): The listing dict from search_listings — the item the user might buy. Uses the title, description, style tags, colors, and category in the prompt.
- `wardrobe` (dict): Has an `items` key with a list of wardrobe pieces. Can be empty.

**What it returns:**
A non-empty string with outfit suggestions. Either specific wardrobe combos or general styling tips if the wardrobe is empty.

**What happens if it fails or returns nothing:**
If `wardrobe['items']` is empty, it switches to a general styling prompt instead of crashing. If the LLM call throws an error, it catches it and returns something like: "Unable to generate outfit suggestions right now. The item is a {category} — try pairing it with complementary basics." So the agent can still move on.

---

### Tool 3: create_fit_card

**What it does:**
Takes the outfit suggestion and writes a short Instagram-style caption for it. Runs at temperature 1.2 so it sounds different each time instead of like a product description. If the outfit string is empty, it returns an error message instead of calling the LLM.

**Input parameters:**
- `outfit` (str): The suggestion from suggest_outfit. Can't be empty.
- `new_item` (dict): Used to pull in the item name, price, and platform.

**What it returns:**
A 2–4 sentence caption that mentions the item, price, and platform once each. Returns an error string if outfit is empty — never crashes.

**What happens if it fails or returns nothing:**
Checks `if not outfit or not outfit.strip()` before doing anything. Returns `"Cannot generate a fit card without an outfit suggestion. Please try your search again."` without touching the LLM. If the LLM itself throws an error, it catches it and returns a fallback string.

---

### Stretch Tool 1: compare_price

**What it does:**
Checks if the item's price is fair by finding similar listings (same category + overlapping style tags) and averaging their prices. No LLM needed — it's just math.

**Input parameters:**
- `item` (dict): The listing being evaluated.

**What it returns:**
A dict with: `verdict` ("great deal", "fair price", or "overpriced"), `item_price`, `avg_comparable_price`, `comparable_count`, and `summary` (a one-line result with an emoji like "👍 Fair Price — $24 vs avg $22 across 14 similar tops").

**What happens if it fails or returns nothing:**
If there's nothing to compare against, returns `verdict="no data"` and a note in summary. Never raises.

---

### Stretch Tool 2: get_trending_styles

**What it does:**
Counts which style tags appear most in the listings dataset. If you pass a size, it only looks at listings in that size. In a real app this would call a fashion API — here it just uses the mock data.

**Input parameters:**
- `size` (str | None): Filter by size first, or pass None to count across all listings.

**What it returns:**
A string with the top 5 style tags, how many listings have each one, and an example item for each. Falls back to all sizes if none match. Never crashes.

---

### Stretch Feature 3: Style profile memory

**What it does:**
Saves the user's wardrobe to `data/style_profile.json` so it comes back next time. The UI has a "Save my wardrobe" button and a "Saved profile" option that loads the file automatically.

**Input/output:**
- `save_style_profile(wardrobe: dict) → str` — success or error message
- `load_style_profile() → dict | None` — wardrobe dict, or None if nothing saved
- `profile_exists() → bool` — used by the UI to show or hide the saved profile option

**What happens if it fails:**
Both functions catch all exceptions and return a fallback value. If the saved profile can't load, the UI falls back to the example wardrobe.

---

## Planning Loop

**How does the agent decide what to do next?**

The loop runs in `run_agent()` and checks what came back at each step before moving on. The one real branching point is after the search — if nothing matches, it stops there.

```
Step 1 — Initialize a fresh session dict for this interaction.

Step 2 — Parse the query with regex:
    - max_price: look for "under $30", "$30", "under 30" → float or None
    - size: look for "size M" or standalone XS/S/M/L/XL/XXL → str or None
    - description: what's left after stripping price and size
    Store in session["parsed"].

Step 3 — Run get_trending_styles(size). [STRETCH]
    Store in session["trending"].
    This always runs — even if the search later finds nothing.

Step 4 — Run search_listings(description, size, max_price).
    Store in session["search_results"].

    If results is empty AND a size was given: [STRETCH retry]
        Retry with size=None.
        Store retry results in session["search_results"].
        Set session["retry_note"] = "No results for size {size} — showing all sizes."

    If still empty:
        Set session["error"] = helpful message with what was searched + what to try.
        return session  ← EARLY EXIT — suggest_outfit and create_fit_card do NOT run.

Step 5 — Pick the top result:
    session["selected_item"] = session["search_results"][0]

Step 6 — Run compare_price(selected_item). [STRETCH]
    Store in session["price_verdict"].

Step 7 — Run suggest_outfit(selected_item, wardrobe).
    Store in session["outfit_suggestion"].

Step 8 — Run create_fit_card(outfit_suggestion, selected_item).
    Store in session["fit_card"].

Step 9 — Return session.
```

The agent doesn't run all tools every time. If the search finds nothing, it stops at Step 4 and returns the error. `get_trending_styles` always runs because trend data is still useful even when the search fails.

---

## State Management

**How does info from one tool get to the next?**

Everything goes into a single `session` dict that gets created at the start of `run_agent()`. Tools don't talk to each other — the planning loop reads from and writes to the session, then passes the right values in as arguments.

| Key | When it's set | What's in it |
|-----|--------------|--------------|
| `session["parsed"]` | Step 2 | description, size, max_price from the raw query |
| `session["trending"]` | Step 3 | trending styles string |
| `session["search_results"]` | Step 4 | list of matching listing dicts |
| `session["selected_item"]` | Step 5 | the top listing dict |
| `session["price_verdict"]` | Step 6 | price comparison result dict |
| `session["outfit_suggestion"]` | Step 7 | outfit ideas string |
| `session["fit_card"]` | Step 8 | the caption string |
| `session["error"]` | Step 4 if no results | error message, None on the happy path |
| `session["retry_note"]` | Step 4 if size retry happened | note that size filter was loosened |

The item from the search and the outfit string from suggest_outfit are passed directly into the next tool — nothing gets re-fetched or re-generated between steps.

---

## Error Handling

| Tool | Failure mode | What the agent does |
|------|-------------|----------------|
| search_listings | No results match | Retries without size filter first (if size was given). If still empty, sets `session["error"]` and returns early. `suggest_outfit` and `create_fit_card` never run. |
| suggest_outfit | Wardrobe is empty | Switches to a different LLM prompt asking for general styling advice instead of wardrobe-specific pairings. Returns a non-empty string either way. |
| create_fit_card | Outfit input is empty | Checks `if not outfit or not outfit.strip()` before touching the LLM. Returns an error string instead of raising. |

---

## Architecture

```
User query (natural language)
    │
    ▼
┌──────────────────────────────────────────────────────────────┐
│                      Planning Loop                            │
│  (run_agent in agent.py)                                     │
│                                                              │
│  Step 2: _parse_query(query)                                 │
│    └─► session["parsed"] = {description, size, price}        │
│                     │                                        │
│  Step 3: [STRETCH] get_trending_styles(size)                 │
│    └─► session["trending"] = trend summary str               │
│        (always runs — useful even on no-results path)        │
│                     │                                        │
│  Step 4: search_listings(description, size, max_price)       │
│    └─► session["search_results"] = [...]                     │
│                     │                                        │
│         ┌───────────┴──────────┐                             │
│    results=[]             results=[...]                      │
│         │                     │                             │
│    [STRETCH retry:        Step 5: selected_item =            │
│     drop size filter]      search_results[0]                 │
│         │                     │                             │
│    still empty?          Step 6: [STRETCH] compare_price(    │
│         │                  selected_item)                    │
│    session["error"]        └─► session["price_verdict"]      │
│    = helpful message              │                          │
│         │                Step 7: suggest_outfit(             │
│    return session ◄─         selected_item, wardrobe)        │
│    (EARLY EXIT)    session["outfit_suggestion"] = str        │
│                              │                              │
│                    wardrobe empty?                          │
│                    ├── yes: general styling prompt          │
│                    └── no: wardrobe-specific prompt         │
│                              │                              │
│                    Step 8: create_fit_card(                 │
│                       outfit_suggestion, selected_item)     │
│                              │                              │
│                    session["fit_card"] = caption str        │
│                              │                              │
│                    Step 9: return session                   │
└──────────────────────────────────────────────────────────────┘
    │                               │
    ▼                               ▼
session["error"]            session["selected_item"]
session["fit_card"]=None    session["outfit_suggestion"]
session["trending"]         session["fit_card"]
                            session["price_verdict"]
                            session["trending"]
                                    │
                                    ▼
                            app.py / handle_query()
                            maps session → 4 UI panels
                  (listing+price | outfit | fit card | trending)

[STRETCH: memory.py]
  save_style_profile(wardrobe) → data/style_profile.json
  load_style_profile()         → wardrobe dict | None
  UI: "Saved profile" radio + "Save my wardrobe" button
```

---

## AI Tool Plan

**Milestone 3 — Tool implementations:**

- **search_listings**: I gave Claude the Tool 1 spec (inputs, scoring approach, return value, what to do on no results) and asked it to implement the function using `load_listings()`. I checked: does it filter by both price and size? Does it score by keyword overlap across all text fields? Does it return `[]` without crashing? I tested with "vintage graphic tee" (should get results), "designer ballgown size XXS under $5" (should return []), and "jacket under $10" (should respect price ceiling). The generated code worked but used one big regex on all fields combined. I split it into separate fields and joined them, which is easier to follow. I also added a set of common noise words to filter out ("a", "the", "for", etc.) because without it they matched everything and inflated scores.

- **suggest_outfit**: I gave Claude the Tool 2 spec and the wardrobe_schema.json structure and asked it to implement with Groq's llama-3.3-70b-versatile. I checked: does it branch on empty vs non-empty wardrobe? Does it name specific wardrobe pieces when the wardrobe has items? Does it handle empty wardrobe without returning an empty string? Tested with both `get_example_wardrobe()` and `get_empty_wardrobe()`.

- **create_fit_card**: I gave Claude the Tool 3 spec and asked it to implement with temperature=1.2 and a guard against empty outfit string. I checked: does it return an error string (not raise) on empty input? Does running the same prompt twice produce different output? Does the caption mention price and platform?

**Milestone 4 — Planning loop:**

I gave Claude the full architecture diagram plus the Planning Loop and State Management sections and asked it to implement `run_agent()`. I checked: does it branch on empty `search_results`? Does it pass `session["selected_item"]` into `suggest_outfit` without re-fetching? Does it pass `session["outfit_suggestion"]` into `create_fit_card` without re-calling? I tested the no-results path with "designer ballgown size XXS under $5" and confirmed `session["fit_card"]` comes back as None.

---

## A Complete Interaction (Step by Step)

FitFindr is an AI agent for thrift shopping. You type what you're looking for in plain English, it searches a mock dataset of secondhand listings, checks if the price is fair, suggests outfit ideas using your wardrobe, and writes a caption you could actually post. If nothing matches, it tells you what to try instead of just breaking.

**Example query:** "vintage graphic tee under $30"

**Step 1 — Parse the query:**
`_parse_query` pulls out:
- `description`: "vintage graphic tee" (after stripping the price part)
- `size`: None (no size mentioned)
- `max_price`: 30.0

session["parsed"] = {"description": "vintage graphic tee", "size": None, "max_price": 30.0}

**Step 2 — Search listings:**
`search_listings("vintage graphic tee", size=None, max_price=30.0)` loads all 40 listings, drops anything over $30, then scores what's left by counting how many keywords match each listing. Something like "Graphic Tee — 2003 Tour Bootleg Style" at $24 with style_tags ["graphic tee", "vintage"] scores high. Returns 3–5 matching dicts sorted by score.

session["search_results"] = [<band-tee dict>, <y2k-tee dict>, ...]
session["selected_item"] = <band-tee dict>  (first result)

**Step 3 — Compare price:**
`compare_price(selected_item)` finds all listings in the same category (tops) with overlapping style tags. Averages their prices. Band tee at $24 vs avg $22 → verdict: "👍 Fair Price — $24.00 vs. avg $22.00 across 14 comparable tops listings". Stored in session["price_verdict"] and shown in the listing panel.

**Step 4 — Suggest outfit:**
`suggest_outfit(selected_item, wardrobe)` is called. The wardrobe has items, so the LLM prompt includes both the band tee details and the wardrobe list. LLM responds with something like: *"This boxy graphic tee pairs perfectly with your baggy straight-leg jeans and chunky white sneakers for a 90s streetwear look. Roll the sleeves once and do a slight front tuck for shape. Or throw your vintage denim jacket on top and switch to combat boots to go more grunge."*

session["outfit_suggestion"] = "This boxy graphic tee pairs perfectly with..."

**Step 5 — Create fit card:**
`create_fit_card(outfit_suggestion, selected_item)` builds a prompt with the outfit and item details ($24, depop). LLM at temp 1.2 responds with: *"thrifted this faded bootleg tee off depop for $24 and it was made for my baggy jeans era 🖤 dark wash denim + chunky sneakers and we're giving full 90s without trying. whole look is under $30 counting the tee"*

session["fit_card"] = "thrifted this faded bootleg tee off depop..."

**Final output — 4 panels in the UI:**
- **Top listing found**: title, price ($24.00), platform (Depop), size, condition, brand, colors, style tags, description, price verdict
- **Outfit idea**: the full outfit suggestion from the LLM
- **Your fit card**: the Instagram caption
- **Trending right now**: top 5 style tags in the dataset (filtered by size if one was given)
