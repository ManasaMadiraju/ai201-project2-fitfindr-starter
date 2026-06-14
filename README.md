# FitFindr

FitFindr is an AI agent for thrift shopping. You type what you're looking for in plain English and it searches a mock dataset of secondhand listings, checks if the price is fair, suggests outfit ideas using your wardrobe, and writes a caption you could actually post. If nothing matches your search, it tells you what to try instead instead of just breaking.

---

## Setup

```bash
pip install -r requirements.txt
```

Create a `.env` file in the project root:

```
GROQ_API_KEY=your_key_here
```

Get a free key at [console.groq.com](https://console.groq.com).

Run the app:

```bash
python app.py
```

Open `http://localhost:7860` in your browser.

---

## Tools

### Tool 1: `search_listings`

**Signature:** `search_listings(description: str, size: str | None, max_price: float | None) → list[dict]`

This is the first tool that runs. It goes through all 40 listings in the dataset and finds ones that match what you're looking for. It first filters out anything over your price limit or the wrong size, then scores the remaining listings by counting how many of your keywords show up in the title, description, style tags, colors, and brand. The best matches come back first.

**Inputs:**
- `description` (str) — what you're looking for, e.g. "vintage graphic tee"
- `size` (str | None) — e.g. "M" or "S/M". Checks if your size appears anywhere in the listing's size field. Pass None to skip size filtering
- `max_price` (float | None) — price ceiling in dollars. Pass None to skip price filtering

**Returns:** A list of listing dicts sorted by best match. Each listing has: `id`, `title`, `description`, `category`, `style_tags`, `size`, `condition`, `price`, `colors`, `brand`, `platform`. Returns an empty list if nothing matches — never crashes.

---

### Tool 2: `suggest_outfit`

**Signature:** `suggest_outfit(new_item: dict, wardrobe: dict) → str`

Takes the item from the search and the user's wardrobe and asks the Groq LLM to suggest 1-2 outfits. If the wardrobe has items, it references specific pieces by name. If the wardrobe is empty, it gives general styling advice instead of failing.

**Inputs:**
- `new_item` (dict) — the listing dict that came out of search_listings
- `wardrobe` (dict) — has an `items` key with a list of wardrobe pieces. Can be empty

**Returns:** A non-empty string with outfit ideas. Always returns something — either specific wardrobe combos or general styling advice if wardrobe is empty.

---

### Tool 3: `create_fit_card`

**Signature:** `create_fit_card(outfit: str, new_item: dict) → str`

Takes the outfit suggestion and writes a short caption like something you'd post on Instagram. It runs at temperature 1.2 so it sounds different each time and doesn't read like a product description. If the outfit string is empty, it returns an error message instead of calling the LLM.

**Inputs:**
- `outfit` (str) — the suggestion string from suggest_outfit. Must not be empty
- `new_item` (dict) — the listing dict, used to pull in the item name, price, and platform

**Returns:** A 2-4 sentence caption that mentions the item, price, and platform once each. Returns an error string if outfit is empty — never crashes.

---

### Tool 4: `compare_price` *(Stretch)*

**Signature:** `compare_price(item: dict) → dict`

Checks if the item's price is fair by finding similar listings in the dataset (same category, overlapping style tags) and averaging their prices. No LLM needed for this one — it's just math.

**Inputs:**
- `item` (dict) — the listing being evaluated

**Returns:** A dict with `verdict` ("great deal", "fair price", or "overpriced"), `item_price`, `avg_comparable_price`, `comparable_count`, and `summary` (a one-line result with an emoji). Returns "no data" if there's nothing to compare against.

---

### Tool 5: `get_trending_styles` *(Stretch)*

**Signature:** `get_trending_styles(size: str | None) → str`

Looks through the listings dataset and counts which style tags show up the most. If you give it a size, it only counts listings in that size. In a real app this would call a fashion API — here it uses the mock dataset.

**Inputs:**
- `size` (str | None) — filter by size before counting, or pass None for all listings

**Returns:** A string showing the top 5 style tags, how many listings have each, and an example item for each one. Falls back to all sizes if none match. Never crashes.

---

### Tool 6: `save_style_profile` / `load_style_profile` *(Stretch — memory.py)*

**Signatures:**
- `save_style_profile(wardrobe: dict) → str`
- `load_style_profile() → dict | None`
- `profile_exists() → bool`

Saves your wardrobe to a JSON file so you don't have to re-enter it next time. The UI has a save button and a "Saved profile" wardrobe option that loads the file automatically.

`save_style_profile` returns a success or error message. `load_style_profile` returns the wardrobe dict or None if no file exists. Nothing here crashes — all exceptions are caught.

---

## How the Planning Loop Works

The loop lives in `run_agent()` in `agent.py`. The key thing about it is that it doesn't just run all the tools every time in the same order. It checks what came back before deciding what to do next.

Here's the actual flow:

```
Step 1 — Start a new session dict to hold everything.

Step 2 — Parse the query with regex to pull out:
    - max_price from phrases like "under $30" or "$30"
    - size from "size M" or standalone M/S/L/XL etc.
    - description = whatever's left after removing price and size

Step 3 — Run get_trending_styles(size) and save the result.
    This always runs, even if the search later finds nothing.

Step 4 — Run search_listings(description, size, max_price).

    If results come back empty AND a size was specified:
        Retry without the size filter.
        Save a note saying the size filter was removed.

    If still empty after retry:
        Save an error message explaining what to try.
        Return early — suggest_outfit and create_fit_card do NOT run.

Step 5 — Pick the top result as the selected item.

Step 6 — Run compare_price(selected_item) and save the verdict.

Step 7 — Run suggest_outfit(selected_item, wardrobe) and save the result.

Step 8 — Run create_fit_card(outfit_suggestion, selected_item) and save the result.

Step 9 — Return the session.
```

The early exit in Step 4 is the main branching point. If the search finds nothing, the agent stops there and returns an error. It never calls suggest_outfit or create_fit_card with empty or None input.

---

## State Management

Everything gets stored in a single `session` dict that's created at the start of each run. Tools don't talk to each other directly — the planning loop reads from and writes to the session, and passes the right values into each tool as arguments.

| Key | When it's set | What's in it |
|-----|--------------|--------------|
| `session["parsed"]` | Step 2 | description, size, max_price extracted from the query |
| `session["trending"]` | Step 3 | trending styles string |
| `session["search_results"]` | Step 4 | list of matching listings |
| `session["selected_item"]` | Step 5 | the top listing dict |
| `session["price_verdict"]` | Step 6 | price comparison result dict |
| `session["outfit_suggestion"]` | Step 7 | outfit ideas string |
| `session["fit_card"]` | Step 8 | the caption string |
| `session["error"]` | Step 4 if no results | error message, None otherwise |
| `session["retry_note"]` | Step 4 if size retry | note that size filter was loosened |

The item from the search (`selected_item`) is the exact same dict that gets passed into `suggest_outfit`. The outfit string from `suggest_outfit` is the exact same string that goes into `create_fit_card`. Nothing gets re-fetched between steps.

---

## Error Handling

### `search_listings` — nothing matches
The tool returns `[]` instead of crashing. The agent checks this right away. If a size was given, it retries without the size filter first. If still empty, it sets a message like:

> "No listings found for 'designer ballgown' in size XXS under $5. Try different keywords, a higher price, or leave out the size filter."

Then it returns early without running the other tools.

**To trigger it:**
```bash
python -c "
from tools import search_listings
print(search_listings('designer ballgown', size='XXS', max_price=5))
"
```

### `suggest_outfit` — wardrobe is empty
Before building the LLM prompt, the tool checks if `wardrobe['items']` is empty. If it is, it switches to a different prompt that asks for general styling advice instead of wardrobe-specific pairings. It still returns something useful — it just doesn't reference pieces the user doesn't have.

**To trigger it:**
```bash
python -c "
from tools import search_listings, suggest_outfit
from utils.data_loader import get_empty_wardrobe
results = search_listings('vintage graphic tee', size=None, max_price=50)
print(suggest_outfit(results[0], get_empty_wardrobe()))
"
```

### `create_fit_card` — outfit string is empty
The tool checks `if not outfit or not outfit.strip()` before doing anything. If that's true, it returns `"Cannot generate a fit card without an outfit suggestion. Please try your search again."` without calling the LLM at all.

**To trigger it:**
```bash
python -c "
from tools import search_listings, create_fit_card
results = search_listings('vintage graphic tee', size=None, max_price=50)
print(create_fit_card('', results[0]))
"
```

---

## Stretch Features

### Retry with fallback
When the search comes back empty and the user gave a size, the agent automatically retries without the size filter. If that works, it shows a warning at the top of the listing panel so the user knows the size constraint was loosened. If it still finds nothing, it shows an error and stops.

### Price comparison
After finding an item, the agent compares its price to similar listings in the dataset. It finds listings in the same category with overlapping style tags and averages their prices. Then it labels the item as a great deal, fair price, or overpriced. The result shows up in the listing panel with an emoji.

### Trend awareness
Before the search runs, the agent counts which style tags appear most often in the dataset (filtered by size if one was given). It shows the top 5 in a dedicated panel. This runs on every query, even if the search finds nothing.

### Style profile memory
You can save your wardrobe to a file using the save button in the UI. Next time you open the app, a "Saved profile" option appears and loads your wardrobe automatically. The save and load functions are in `memory.py` and catch any errors so they never crash the app.

---

## Spec Reflection

The spec helped most with error handling. Before writing any code, I had to decide what each tool should return when something goes wrong — a string, an empty list, None, or an exception. Deciding up front that `suggest_outfit` and `create_fit_card` should always return a string (never raise) made the planning loop a lot simpler. I didn't have to add extra checks every time I called those tools.

One thing that didn't go as planned was the query parsing. I originally thought I could extract the price and size in one regex pass. In practice that didn't work — the price number would sometimes get matched as a size (e.g., "$30" matching "30" as a size). I had to do it in two separate passes: extract and remove the price first, then look for the size in what's left.

---

## AI Usage

### search_listings implementation
I gave Claude the Tool 1 section from planning.md — the inputs, what it should return, and what to do on no results — and asked it to implement the function using `load_listings()`. The generated code mostly matched the spec but used one big regex on all text fields combined. I split that into a list of separate fields and joined them, which is easier to follow. I also added a set of noise words to filter out ("a", "the", "for", etc.) because without it, those words were matching every single listing and inflating scores.

### Planning loop implementation
I gave Claude the architecture diagram and the planning loop section from planning.md and asked it to implement `run_agent()`. The loop logic came out correct — it branched on empty results and passed state through the session dict. But `_parse_query()` had a bug where the price number was sometimes getting caught by the size regex. I fixed it by running the two extractions in order — price first, then size on the cleaned string.

### Writing tests
I gave Claude the specs for all three tools and asked for pytest tests covering the failure modes. The generated tests covered the basics. I added `test_search_result_structure` to make sure every result dict has all the required fields, and `test_search_no_size_filter_returns_more` to confirm that removing the size filter actually expands results — both would catch real regressions.
