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

Step 3 — Call search_listings(description, size, max_price).
    Store in session["search_results"].

    IF results is empty AND size was provided:
        Retry: search_listings(description, None, max_price)   ← loosened
        Set session["retry_note"] = "No results for size X — showing all sizes."

    IF results is still empty:
        session["error"] = descriptive message
        return session   ← EARLY EXIT (suggest_outfit and create_fit_card NOT called)

Step 4 — session["selected_item"] = results[0]

Step 5 — Call suggest_outfit(selected_item, wardrobe).
    Store in session["outfit_suggestion"].

Step 6 — Call create_fit_card(outfit_suggestion, selected_item).
    Store in session["fit_card"].

Step 7 — Return session.
```

The key decision point is after Step 3: if `search_listings` returns an empty list (even after the size-relaxed retry), the agent terminates early with an informative error. This prevents calling `suggest_outfit` with a `None` item or `create_fit_card` with a `None` outfit — both of which would produce meaningless or crashing outputs.

---

## State Management

All state lives in a single `session` dict initialized by `_new_session()` at the start of each `run_agent()` call. Tools do not call each other and do not share global state — each tool receives exactly what it needs as function arguments sourced from the session.

| Key | Set in step | What it holds | Used by |
|-----|------------|---------------|---------|
| `session["parsed"]` | Step 2 | `{description, size, max_price}` from query | Step 3 (search) |
| `session["search_results"]` | Step 3 | list of matching listing dicts | Step 4 (select top) |
| `session["selected_item"]` | Step 4 | single listing dict (results[0]) | Steps 5 and 6 |
| `session["outfit_suggestion"]` | Step 5 | string from `suggest_outfit` | Step 6 |
| `session["fit_card"]` | Step 6 | caption string from `create_fit_card` | Returned to UI |
| `session["error"]` | Step 3 (if no results) | error string; `None` on success | app.py / UI |
| `session["retry_note"]` | Step 3 (retry) | note about loosened size filter | UI listing panel |

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

## Stretch Feature: Retry with Fallback

Implemented in `run_agent()` (Steps 3–4 of the planning loop). When `search_listings` returns an empty list **and** the user specified a size, the agent automatically retries with the size filter removed. If the retry finds results, the agent proceeds normally and sets `session["retry_note"]` to inform the user that results are for all sizes. This note appears at the top of the listing panel in the UI. The user is never left with a confusing empty result when a minor constraint relaxation would find something.

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
