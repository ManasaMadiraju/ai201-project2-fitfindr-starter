# FitFindr

A multi-tool AI agent that helps users find secondhand pieces and figure out how to wear them. Given a natural language request, FitFindr searches mock thrift listings, evaluates fit against an existing wardrobe, and generates a shareable outfit caption — while handling failures gracefully at every step.

---

## Setup

```bash
pip install -r requirements.txt
```

Create a `.env` file in the project root (already in `.gitignore` — never commit it):

```
GROQ_API_KEY=your_key_here
```

Get a free key at [console.groq.com](https://console.groq.com) — no credit card required.

Run the app:

```bash
python app.py
```

Open the URL shown in your terminal (usually `http://localhost:7860`).

---

## Tool Inventory

### Tool 1: `search_listings`

**Function signature:** `search_listings(description: str, size: str | None, max_price: float | None) → list[dict]`

**Purpose:** Searches the 40-item mock listings dataset for secondhand pieces matching the user's keyword description. Filters by price and size when provided, then ranks remaining items by keyword overlap across title, description, category, style_tags, colors, and brand.

**Inputs:**
- `description` (str) — keyword phrase describing the item (e.g., `"vintage graphic tee"`)
- `size` (str | None) — size string for case-insensitive substring filtering against each listing's `size` field; `None` skips size filtering
- `max_price` (float | None) — price ceiling in USD (inclusive); `None` skips price filtering

**Output:** `list[dict]` — matching listing dicts sorted by relevance score (highest first). Each dict has: `id`, `title`, `description`, `category`, `style_tags` (list), `size`, `condition`, `price` (float), `colors` (list), `brand`, `platform`. Returns `[]` on no match — never raises.

---

### Tool 2: `suggest_outfit`

**Function signature:** `suggest_outfit(new_item: dict, wardrobe: dict) → str`

**Purpose:** Calls the Groq LLM to suggest 1–2 complete outfit combinations using the thrifted item and the user's existing wardrobe. When the wardrobe is empty, falls back to general styling advice instead of crashing.

**Inputs:**
- `new_item` (dict) — a listing dict from `search_listings` output
- `wardrobe` (dict) — a dict with an `items` key containing a list of wardrobe item dicts; may have an empty `items` list

**Output:** Non-empty string (3–6 sentences) with outfit suggestions. When wardrobe has items, names specific wardrobe pieces. When empty, describes what kinds of basics pair well and what aesthetic suits the item.

---

### Tool 3: `create_fit_card`

**Function signature:** `create_fit_card(outfit: str, new_item: dict) → str`

**Purpose:** Generates a 2–4 sentence Instagram/TikTok-style OOTD caption for the thrifted find. Uses LLM temperature=1.2 so outputs vary meaningfully across different inputs. Feels like a real person's post, not a product description.

**Inputs:**
- `outfit` (str) — the outfit suggestion string from `suggest_outfit`; must be non-empty
- `new_item` (dict) — the listing dict for the thrifted item (uses `title`, `price`, `platform`)

**Output:** 2–4 sentence caption string mentioning item name, price, and platform each once. Returns a descriptive error string (not an exception) if `outfit` is empty or whitespace-only.

### Tool 4: `compare_price` *(Stretch)*

**Function signature:** `compare_price(item: dict) → dict`

**Purpose:** Estimates whether a listing's price is fair by comparing it against similar items in the dataset (same category + overlapping style tags). Pure Python — no LLM needed.

**Inputs:**
- `item` (dict) — a listing dict (the item being evaluated)

**Output:** A dict with `verdict` (str: "great deal" / "fair price" / "overpriced" / "no data"), `item_price` (float), `avg_comparable_price` (float | None), `comparable_count` (int), `summary` (str — one-line human-readable assessment with emoji). Never raises.

---

### Tool 5: `get_trending_styles` *(Stretch)*

**Function signature:** `get_trending_styles(size: str | None) → str`

**Purpose:** Analyzes the listings dataset to surface which style tags appear most frequently. Optionally filters to listings available in the given size first. In production this would call a fashion API; here the mock dataset serves as proxy.

**Inputs:**
- `size` (str | None) — filters listings to this size before counting tags; `None` uses all listings

**Output:** Formatted string listing top 5 trending style tags with counts and an example item each. Falls back gracefully to all sizes if the given size yields no listings. Never raises.

---

### Tool 6: `save_style_profile` / `load_style_profile` *(Stretch — memory.py)*

**Function signatures:**
- `save_style_profile(wardrobe: dict) → str`
- `load_style_profile() → dict | None`
- `profile_exists() → bool`

**Purpose:** Persists a user's wardrobe to `data/style_profile.json` so it's available across sessions. The UI exposes a "Saved profile" wardrobe option and a "💾 Save current wardrobe" button.

**Output:** `save_style_profile` returns a success/error message string. `load_style_profile` returns the wardrobe dict or `None` if no profile exists. All functions catch exceptions and never raise.

---

## How the Planning Loop Works

The loop in `run_agent()` (`agent.py`) uses a **conditional sequence** — it does not call all three tools unconditionally. Here is the actual branching logic:

```
Step 1 — Initialize session dict (_new_session).

Step 2 — Parse query with regex:
    Extract max_price ("under $30", "$30", "max 30") → float or None
    Extract size ("size M", or standalone XS/S/M/L/XL/XXL) → str or None
    Remove extracted fragments → description str
    Store in session["parsed"].

Step 3 — [STRETCH] Call get_trending_styles(size).
    Store in session["trending"].
    Always runs — trending context is useful even when search returns nothing.

Step 4 — Call search_listings(description, size, max_price).
    Store in session["search_results"].

    IF results is empty AND size was provided:
        [STRETCH] Retry: search_listings(description, None, max_price)
        Set session["retry_note"] = "No results for size X — showing all sizes."

    IF results is still empty:
        session["error"] = descriptive message
        return session   ← EARLY EXIT (compare_price, suggest_outfit, create_fit_card NOT called)

Step 5 — session["selected_item"] = results[0]

Step 6 — [STRETCH] Call compare_price(selected_item).
    Store in session["price_verdict"].

Step 7 — Call suggest_outfit(selected_item, wardrobe).
    Store in session["outfit_suggestion"].

Step 8 — Call create_fit_card(outfit_suggestion, selected_item).
    Store in session["fit_card"].

Step 9 — Return session.
```

The key decision point is after Step 3: if `search_listings` returns an empty list (even after the size-relaxed retry), the agent terminates early with an informative error. This prevents calling `suggest_outfit` with a `None` item or `create_fit_card` with a `None` outfit — both of which would produce meaningless or crashing outputs.

---

## State Management

All state lives in a single `session` dict initialized by `_new_session()` at the start of each `run_agent()` call. Tools do not call each other and do not share global state — each tool receives exactly what it needs as function arguments sourced from the session.

| Key | Set in step | What it holds | Used by |
|-----|------------|---------------|---------|
| `session["parsed"]` | Step 2 | `{description, size, max_price}` from query | Step 4 (search) |
| `session["trending"]` | Step 3 | trend summary string from `get_trending_styles` | UI trending panel |
| `session["search_results"]` | Step 4 | list of matching listing dicts | Step 5 (select top) |
| `session["selected_item"]` | Step 5 | single listing dict (results[0]) | Steps 6, 7, 8 |
| `session["price_verdict"]` | Step 6 | dict from `compare_price` (verdict, avg, summary) | UI listing panel |
| `session["outfit_suggestion"]` | Step 7 | string from `suggest_outfit` | Step 8 |
| `session["fit_card"]` | Step 8 | caption string from `create_fit_card` | Returned to UI |
| `session["error"]` | Step 4 (if no results) | error string; `None` on success | app.py / UI |
| `session["retry_note"]` | Step 4 (retry) | note about loosened size filter | UI listing panel |

State visibly passes between tools: `session["selected_item"]` is the exact same dict object passed into `suggest_outfit` in Step 5. `session["outfit_suggestion"]` is the exact same string passed into `create_fit_card` in Step 6. No re-fetching, no re-prompting the user.

---

## Error Handling Strategy

### `search_listings` — No results match the query
The tool always returns `[]` on no match rather than raising. The planning loop checks `if not results` immediately after the call. Before surfacing an error to the user, it attempts one retry with the size filter removed (stretch feature). If still empty, `session["error"]` is set to a specific, actionable message, e.g.:

> *"No listings found for "designer ballgown" in size XXS under $5. Try different keywords, a higher price ceiling, or leave out the size filter."*

The agent returns immediately — `suggest_outfit` and `create_fit_card` are never called with empty input.

**Triggered example:** Running `python agent.py` with query `"designer ballgown size XXS under $5"` produces this error message and leaves `session["fit_card"]` as `None`.

### `suggest_outfit` — Wardrobe is empty
The tool detects `if not wardrobe.get("items")` before building the LLM prompt. When the list is empty, it sends a different prompt asking for general styling advice (what basics pair well, what aesthetic the item suits) instead of trying to reference specific wardrobe pieces. This means the tool returns a useful, non-empty string for new users who haven't filled in their wardrobe yet.

**Triggered example:**
```bash
python -c "
from tools import search_listings, suggest_outfit
from utils.data_loader import get_empty_wardrobe
results = search_listings('vintage graphic tee', size=None, max_price=50)
print(suggest_outfit(results[0], get_empty_wardrobe()))
"
```
Returns general styling advice rather than an empty string or exception.

### `create_fit_card` — Empty or whitespace-only outfit string
The tool checks `if not outfit or not outfit.strip()` before calling the LLM. If the guard triggers, it returns: *"Cannot generate a fit card without an outfit suggestion. Please try your search again."* No LLM call is made. LLM API errors are also caught with a try/except and return a fallback string.

**Triggered example:**
```bash
python -c "
from tools import search_listings, create_fit_card
results = search_listings('vintage graphic tee', size=None, max_price=50)
print(create_fit_card('', results[0]))
"
```
Returns the error message string without raising.

---

## Stretch Features

### Retry with fallback
When `search_listings` returns empty **and** the user specified a size, the agent retries with the size filter removed. On success it sets `session["retry_note"]` and surfaces a warning in the listing panel. If still empty after retry, the agent exits early with an actionable error.

### Price comparison (`compare_price`)
Called in Step 6 immediately after selecting the top result. Finds comparable listings (same category + overlapping style tags), computes their average price, and labels the item ✅ Great Deal, 👍 Fair Price, or ⚠️ Overpriced. The verdict is embedded in the listing panel alongside the item details.

### Trend awareness (`get_trending_styles`)
Called in Step 3 on every query — before the search, so trend context is available even on the no-results path. Counts style tag frequency across the dataset (filtered by size when provided) and returns the top 5 trending styles with listing counts and example items. Displayed in the dedicated **🔥 Trending right now** panel.

### Style profile memory (`memory.py`)
`save_style_profile(wardrobe)` writes the user's wardrobe dict + a timestamp to `data/style_profile.json`. `load_style_profile()` reads it back. The UI exposes a **💾 Save current wardrobe** button and a **Saved profile** wardrobe option that loads the persisted wardrobe automatically on the next session.

---

## Spec Reflection

**One way the spec helped:** Writing the error handling table in `planning.md` before touching any code forced a concrete decision about what each tool should return on failure (an informative string vs. an exception vs. `None`). That decision — *always return a string from suggest_outfit and create_fit_card* — made the planning loop much simpler to write because it never needed to check whether the tool output was truthy before proceeding.

**One way implementation diverged from the spec:** The initial spec described query parsing as a single regex pass. In practice, extracting max_price and size in separate passes (price first, then size, operating on a progressively cleaned string) was necessary to avoid capturing price digits as size values (e.g., "$30" triggering a size match on "30"). The spec described the intent correctly but underspecified the ordering dependency between the two extractions.

---

## AI Usage

### Instance 1 — Implementing `search_listings`
I gave Claude the Tool 1 spec block from `planning.md` (inputs with types, return value structure including all field names, failure mode requiring `[]` not exception, and the keyword-scoring approach). I asked it to implement the function using `load_listings()` and regex-based tokenization. The generated code matched the spec on filtering and scoring but used a single combined regex on all text fields at once. I revised it to build a list of text parts and join them, which is easier to read and extend. I also added the noise-word set to prevent common words ("I", "for", "a") from inflating scores on every listing.

### Instance 2 — Implementing the planning loop
I gave Claude the full Architecture diagram from `planning.md` plus the Planning Loop and State Management sections. I asked it to implement `run_agent()` and `_parse_query()`. The generated planning loop matched the conditional branching I designed. However, the generated `_parse_query` used a single combined regex that sometimes captured size digits from the price match. I fixed the ordering: extract and remove price first, then search the cleaned string for size — which matched the approach I'd noted in the spec reflection above.

### Instance 3 — Writing pytest tests
I gave Claude the three tool specs (inputs, return values, all three failure modes) and asked it to write pytest tests covering at least one test per failure mode. The generated tests covered the happy path and the three documented failure modes. I added two additional tests: `test_search_no_size_filter_returns_more` (to verify that removing size filter genuinely expands results) and `test_search_result_structure` (to verify every result dict has the required fields), because these would catch regressions if the data loader changed.
