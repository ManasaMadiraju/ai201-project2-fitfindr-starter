# FitFindr — planning.md

> Complete this document before writing any implementation code.
> Your spec and agent diagram are what you'll use to direct AI tools (Claude, Copilot, etc.) to generate your implementation — the more specific they are, the more useful the generated code will be.
> Your planning.md will be reviewed as part of your submission.
> Update it before starting any stretch features.

---

## Tools

List every tool your agent will use. For each tool, fill in all four fields.
You must have at least 3 tools. The three required tools are listed — add any additional tools below them.

### Tool 1: search_listings

**What it does:**
Searches the mock listings dataset (`data/listings.json`) for secondhand items that match the user's keyword description, optional size filter, and optional price ceiling. Returns results ranked by relevance so the best match appears first.

**Input parameters:**
- `description` (str): Keywords describing the item the user wants (e.g., "vintage graphic tee", "90s track jacket"). Used to score listings by keyword overlap against title, description, category, style_tags, colors, and brand fields.
- `size` (str | None): Size string to filter by, e.g. `"M"`, `"S/M"`, `"XL"`. Case-insensitive substring match against the listing's `size` field. `None` means no size filter is applied.
- `max_price` (float | None): Maximum price in USD (inclusive). Listings with `price > max_price` are excluded. `None` means no price filter.

**What it returns:**
A `list[dict]` of matching listing dicts, sorted by relevance score (highest first). Each dict contains: `id` (str), `title` (str), `description` (str), `category` (str — one of tops/bottoms/outerwear/shoes/accessories), `style_tags` (list[str]), `size` (str), `condition` (str — excellent/good/fair), `price` (float), `colors` (list[str]), `brand` (str or None), `platform` (str — depop/thredUp/poshmark). Returns `[]` (empty list) if nothing matches — never raises an exception.

**What happens if it fails or returns nothing:**
The agent checks `if not results` immediately after calling this tool. If the list is empty, the agent first retries with the size filter removed (stretch feature — retry with loosened constraints) and informs the user. If still empty, the agent sets `session["error"]` to a message like: *"No listings found for 'designer ballgown' in size XXS under $5. Try different keywords, a higher price, or skip the size filter."* — then returns the session early without calling `suggest_outfit` or `create_fit_card`.

---

### Tool 2: suggest_outfit

**What it does:**
Given a specific secondhand listing and the user's current wardrobe, calls the Groq LLM (llama-3.3-70b-versatile) to suggest 1–2 complete outfit combinations. When the wardrobe is empty, it falls back to general styling advice for the item instead of crashing.

**Input parameters:**
- `new_item` (dict): A single listing dict from `search_listings` output (the item the user is considering buying). Uses `title`, `description`, `style_tags`, `colors`, and `category` fields in the prompt.
- `wardrobe` (dict): A wardrobe dict with an `items` key containing a list of wardrobe item dicts. Each wardrobe item has `id`, `name`, `category`, `colors`, `style_tags`, and `notes`. May have an empty `items` list — must be handled gracefully.

**What it returns:**
A non-empty string (2–6 sentences) with outfit suggestions. If the wardrobe has items, the response names specific wardrobe pieces to pair with the new item and describes the overall look/vibe. If the wardrobe is empty, it provides general styling advice (what kinds of basics pair well, what aesthetic the item suits) without referencing specific wardrobe pieces.

**What happens if it fails or returns nothing:**
If `wardrobe['items']` is empty, the tool switches to a general-styling prompt rather than raising an error. If the LLM call itself throws an exception (e.g., API error), the tool catches it and returns the string `"Unable to generate outfit suggestions at this time. The item you selected is a {category} — consider pairing it with complementary basics."` so the agent can still attempt `create_fit_card` with the fallback text.

---

### Tool 3: create_fit_card

**What it does:**
Generates a short (2–4 sentence) Instagram/TikTok-style caption for the thrifted outfit. Calls the Groq LLM at higher temperature (1.2) so output varies meaningfully across different inputs. The caption should feel authentic and conversational, not like a product listing.

**Input parameters:**
- `outfit` (str): The outfit suggestion string returned by `suggest_outfit`. Must be non-empty; if empty or whitespace-only, the tool returns an error string without calling the LLM.
- `new_item` (dict): The listing dict for the thrifted item. Used to pull `title`, `price`, and `platform` into the caption naturally.

**What it returns:**
A 2–4 sentence string suitable as an OOTD caption — casual tone, mentions item name + price + platform once each, captures the outfit vibe with specific language. Returns a descriptive error string (not an exception) if `outfit` is empty: `"Cannot generate a fit card without an outfit suggestion. Please try your search again."`.

**What happens if it fails or returns nothing:**
If `outfit` is empty or whitespace-only, returns the error string above immediately without calling the LLM. If the LLM throws an exception, catches it and returns `"Fit card unavailable — check your API key and try again."` The agent displays whatever string this tool returns; it does not re-raise the error.

---

### Additional Tools (if any)

*(Stretch feature: retry with fallback is handled inside the planning loop rather than as a separate tool — see Planning Loop section.)*

---

### Stretch Tool 1: compare_price *(Price comparison)*

**What it does:**
Given a listing, finds comparable items in the dataset (same category + overlapping style tags) and estimates whether the price is fair. Pure Python — no LLM needed.

**Input parameters:**
- `item` (dict): A listing dict (the item the user is considering buying)

**What it returns:**
A dict with: `verdict` (str — "great deal", "fair price", or "overpriced"), `item_price` (float), `avg_comparable_price` (float), `comparable_count` (int), `summary` (str — human-readable one-line assessment with emoji).

**What happens if it fails or returns nothing:**
If no comparables exist (e.g., only one item of that category), returns `verdict="no data"` and a message in `summary`. Never raises.

---

### Stretch Tool 2: get_trending_styles *(Trend awareness)*

**What it does:**
Analyzes the listings dataset to surface which style tags appear most frequently. If a size is provided, filters to listings available in that size first. In a real implementation this would call an external fashion API; here it uses the mock dataset as a proxy.

**Input parameters:**
- `size` (str | None): Size to filter listings by before counting tags; `None` uses all listings

**What it returns:**
A formatted string listing the top 5 trending style tags with their listing counts and an example item for each.

**What happens if it fails or returns nothing:**
Returns a fallback string ("No trend data available") rather than raising.

---

### Stretch Feature 3: Style profile memory

**What it does:**
Saves the user's wardrobe to `data/style_profile.json` so it persists across sessions. `save_style_profile(wardrobe)` writes the file; `load_style_profile()` reads it back. The UI exposes a "Saved profile" wardrobe option and a "Save my wardrobe" button.

**Input/output:**
- `save_style_profile(wardrobe: dict) → str` — returns a success/error message
- `load_style_profile() → dict | None` — returns wardrobe dict or None if no profile saved
- `profile_exists() → bool` — used by the UI to show/hide the saved profile option

**What happens if it fails:**
Both functions catch all exceptions and return a fallback string/None. The UI falls back to the example wardrobe if the saved profile can't be loaded.

---

## Planning Loop

**How does your agent decide which tool to call next?**

The planning loop in `run_agent()` follows a strict conditional sequence with one early-exit branch:

```
Step 1 — Initialize session dict with _new_session(query, wardrobe).

Step 2 — Parse query with _parse_query(query):
    Use regex to extract:
      - max_price: match "under $30", "$30", or "under 30" → float or None
      - size: match "size M" or standalone XS/S/M/L/XL/XXL → str or None
      - description: original query with price/size fragments removed
    Store result in session["parsed"].

Step 3 — [STRETCH] Call get_trending_styles(size).
    Store string in session["trending"].

Step 4 — Call search_listings(description, size, max_price).
    Store list in session["search_results"].

    if results is empty AND size was provided (stretch retry):
        retry search_listings(description, None, max_price)  ← size filter removed
        store retry results in session["search_results"]
        set session["retry_note"] = "No results for size {size} — showing all sizes."

    if results is still empty:
        set session["error"] = helpful message with what was searched + what to try
        return session  ← EARLY EXIT — do NOT call suggest_outfit or create_fit_card

Step 5 — Select top result:
    session["selected_item"] = session["search_results"][0]

Step 6 — [STRETCH] Call compare_price(selected_item).
    Store dict in session["price_verdict"].

Step 7 — Call suggest_outfit(selected_item, wardrobe).
    Store string in session["outfit_suggestion"].

Step 8 — Call create_fit_card(outfit_suggestion, selected_item).
    Store string in session["fit_card"].

Step 9 — Return session.
```

The agent does **not** call all tools unconditionally. The key branch is after Step 4: if `search_listings` returns an empty list (even after retry), the agent sets an error and returns immediately — `compare_price`, `suggest_outfit`, and `create_fit_card` are never called. `get_trending_styles` always runs since trend context is useful even when no item is found.

---

## State Management

**How does information from one tool get passed to the next?**

A single `session` dict is initialized at the start of `run_agent()` and passed by reference through the entire loop. It is the only source of truth for the interaction.

What is stored and when:
- `session["parsed"]` — set in Step 2; contains `description`, `size`, `max_price` extracted from the raw query
- `session["search_results"]` — set in Step 3; list of matching listing dicts from `search_listings`
- `session["selected_item"]` — set in Step 4; the single dict at index 0 of `search_results`. This exact dict object is passed directly into `suggest_outfit` and `create_fit_card` — no re-lookup, no re-entry from the user.
- `session["outfit_suggestion"]` — set in Step 5; the string returned by `suggest_outfit`. Passed directly into `create_fit_card` as the `outfit` argument.
- `session["fit_card"]` — set in Step 6; final output string.
- `session["error"]` — set if an early exit occurs; left as `None` on the happy path.
- `session["retry_note"]` — optionally set in the retry branch; surfaced in the UI listing panel.

Tools do not call each other or share a global state object. Each tool receives exactly what it needs as function arguments, sourced from the session dict in the planning loop.

---

## Error Handling

For each tool, describe the specific failure mode you're handling and what the agent does in response.

| Tool | Failure mode | Agent response |
|------|-------------|----------------|
| search_listings | No results match the query | Agent first retries with size filter removed (if size was given). If still empty, sets `session["error"]` to: *"No listings found for '{description}' [in size {size}] [under ${price}]. Try different keywords, a higher price, or skip the size filter."* Returns session early. `suggest_outfit` and `create_fit_card` are never called. |
| suggest_outfit | Wardrobe is empty (`wardrobe['items'] == []`) | Tool detects empty items list and switches to a different LLM prompt asking for general styling advice rather than wardrobe-specific pairings. Returns a non-empty string describing what aesthetics the item suits and what kinds of pieces pair well with it. Never raises an exception. |
| create_fit_card | Outfit input is empty or whitespace-only string | Tool checks `if not outfit or not outfit.strip()` before calling LLM. Returns the string `"Cannot generate a fit card without an outfit suggestion. Please try your search again."` — never raises an exception. |

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

**Milestone 3 — Individual tool implementations:**

- **search_listings**: I'll give Claude the Tool 1 spec block from this planning.md (inputs, scoring approach, return value, failure mode) and ask it to implement the function using `load_listings()` from the data loader. I'll verify: does it filter by both price and size? Does it score by keyword overlap across all text fields (title, description, category, style_tags, colors, brand)? Does it return `[]` on no match without raising? I'll test it with 3 queries: "vintage graphic tee" (should return results), "designer ballgown size XXS under $5" (should return []), and "jacket under $10" (should respect price filter).

- **suggest_outfit**: I'll give Claude the Tool 2 spec and the wardrobe_schema.json structure and ask it to implement using Groq's llama-3.3-70b-versatile. I'll verify: does it branch on empty vs non-empty wardrobe? Does it reference specific wardrobe item names in the non-empty case? Does it handle the empty case without returning an empty string? I'll test with both `get_example_wardrobe()` and `get_empty_wardrobe()`.

- **create_fit_card**: I'll give Claude the Tool 3 spec and ask it to implement with temperature=1.2 and a guard against empty outfit string. I'll verify: does it return an error string (not raise) on empty input? Does it run the same prompt twice and produce meaningfully different outputs? Does the caption mention price and platform naturally?

**Milestone 4 — Planning loop and state management:**

I'll give Claude the full Architecture diagram from this file plus the Planning Loop and State Management sections and ask it to implement `run_agent()`. I'll verify: does it branch on empty `search_results`? Does it pass `session["selected_item"]` (not a re-lookup) into `suggest_outfit`? Does it pass `session["outfit_suggestion"]` (not a re-call) into `create_fit_card`? I'll print `session["selected_item"]` and confirm it's the exact same dict going into `suggest_outfit`. I'll test the no-results path with "designer ballgown size XXS under $5" and confirm `session["fit_card"]` is `None`.

---

## A Complete Interaction (Step by Step)

FitFindr is an AI agent that takes a plain-English thrift request, searches a mock secondhand dataset for matching listings, evaluates whether the price is fair, and uses the Groq LLM to suggest outfit combinations and generate a shareable Instagram-style caption — all in a single session with no re-entry from the user. If the search returns nothing (even after retrying with loosened size constraints), the agent stops early and tells the user what to try differently rather than passing empty input into the downstream LLM tools.

**Example user query:** "I'm looking for a vintage graphic tee under $30. I mostly wear baggy jeans and chunky sneakers. What's out there and how would I style it?"

**Step 1 — Parse query:**
`_parse_query` extracts:
- `description`: "I'm looking for a vintage graphic tee. I mostly wear baggy jeans and chunky sneakers. What's out there and how would I style it?" (price fragment stripped)
- `size`: `None` (no size mentioned)
- `max_price`: `30.0`

session["parsed"] = {"description": "...", "size": None, "max_price": 30.0}

**Step 2 — Search listings:**
`search_listings("vintage graphic tee ...", size=None, max_price=30.0)` loads all 40 listings, filters to those with price ≤ $30, then scores each remaining listing by counting overlapping keywords ("vintage", "graphic", "tee", etc.) against title/description/style_tags/category/colors/brand. Items like "Graphic Tee — 2003 Tour Bootleg Style" ($24, style_tags include "graphic tee", "vintage") score highest. Returns a list of 3–5 matching dicts sorted by score.

session["search_results"] = [<band-tee dict>, <y2k-tee dict>, ...]
session["selected_item"] = <band-tee dict>  (index 0, top match)

**Step 3 — Compare price:**
`compare_price(selected_item=<band-tee dict>)` finds all listings in the same category (tops) with overlapping style tags. Computes average price of 14 comparable tops. Band tee at $24 vs avg $22 → verdict: "👍 Fair Price — $24.00 vs. avg $22.00 across 14 comparable tops listings". Stored in session["price_verdict"], embedded in listing panel.

**Step 4 — Suggest outfit:**
`suggest_outfit(selected_item=<band-tee dict>, wardrobe=get_example_wardrobe())` is called. The wardrobe has 10 items, so the non-empty branch runs. The LLM prompt includes the band tee's details and lists all 10 wardrobe items. LLM responds: *"This boxy graphic tee pairs perfectly with your baggy straight-leg jeans (dark wash) and chunky white sneakers for a classic 90s streetwear look. Roll the sleeves once and tuck just the front corner slightly for shape. Alternatively, layer your vintage black denim jacket over it and swap the sneakers for black combat boots to go more grunge."*

session["outfit_suggestion"] = "This boxy graphic tee pairs perfectly with..."

**Step 5 — Create fit card:**
`create_fit_card(outfit="This boxy graphic tee pairs perfectly...", new_item=<band-tee dict>)` builds a prompt with the outfit description and item details ($24, depop). LLM at temperature 1.2 responds with: *"thrifted this faded bootleg tee off depop for $24 and it was literally made for my baggy jeans era 🖤 dark wash denim + chunky sneakers and we're giving full 90s without even trying. whole look is under $30 counting the tee"*

session["fit_card"] = "thrifted this faded bootleg tee off depop..."

**Final output to user:**
Four panels in the Gradio UI:
- **Top listing found**: title, price ($24.00), platform (Depop), size (L), condition (Good), brand (Unknown), colors (black), style tags, full description, and price verdict ("👍 Fair Price — $24.00 vs. avg $22.00")
- **Outfit idea**: the full outfit suggestion paragraph from the LLM
- **Your fit card**: the 2–3 sentence Instagram caption
- **Trending right now**: top 5 style tags in the dataset (filtered by size if provided)
