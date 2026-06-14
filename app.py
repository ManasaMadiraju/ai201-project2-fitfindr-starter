"""
app.py

Gradio interface for FitFindr. Includes all stretch features:
  - Price comparison verdict embedded in listing panel
  - Trending styles panel
  - Style profile memory (save / load across sessions)

Run with:
    python app.py
"""

import gradio as gr

from agent import run_agent
from memory import save_style_profile, load_style_profile, profile_exists, profile_saved_at
from utils.data_loader import get_example_wardrobe, get_empty_wardrobe


# ── query handler ─────────────────────────────────────────────────────────────

def handle_query(user_query: str, wardrobe_choice: str) -> tuple[str, str, str, str]:
    """
    Called by Gradio when the user submits a query.

    Returns:
        (listing_text, outfit_suggestion, fit_card, trending_text)
    """
    if not user_query or not user_query.strip():
        return "Please enter a search query to get started.", "", "", ""

    # Select wardrobe
    if wardrobe_choice == "Saved profile":
        wardrobe = load_style_profile()
        if wardrobe is None:
            wardrobe = get_example_wardrobe()
            profile_note = "⚠️  No saved profile found — using example wardrobe.\n\n"
        else:
            saved_at = profile_saved_at() or "unknown time"
            profile_note = f"✅  Loaded your saved profile (saved {saved_at[:10]}).\n\n"
    elif wardrobe_choice == "Empty wardrobe (new user)":
        wardrobe = get_empty_wardrobe()
        profile_note = ""
    else:
        wardrobe = get_example_wardrobe()
        profile_note = ""

    session = run_agent(user_query.strip(), wardrobe)

    # Trending panel — always available regardless of search outcome
    trending_text = session.get("trending") or "Trend data unavailable."

    if session["error"]:
        return session["error"], "", "", trending_text

    # Format listing panel
    item = session["selected_item"]
    brand_text = item.get("brand") or "Unknown brand"
    colors_text = ", ".join(item.get("colors", []))
    tags_text = ", ".join(item.get("style_tags", []))

    listing_text = (
        f"{item['title']}\n"
        f"\n"
        f"Price:     ${item['price']:.2f}\n"
        f"Platform:  {item['platform'].title()}\n"
        f"Size:      {item['size']}\n"
        f"Condition: {item['condition'].title()}\n"
        f"Brand:     {brand_text}\n"
        f"Colors:    {colors_text}\n"
        f"Style:     {tags_text}\n"
        f"\n"
        f"{item['description']}"
    )

    # Embed price verdict
    if session.get("price_verdict"):
        listing_text += f"\n\n{session['price_verdict']['summary']}"

    # Prepend notes
    if session.get("retry_note"):
        listing_text = f"⚠️  {session['retry_note']}\n\n" + listing_text
    if profile_note:
        listing_text = profile_note + listing_text

    return listing_text, session["outfit_suggestion"], session["fit_card"], trending_text


# ── memory handlers ───────────────────────────────────────────────────────────

def handle_save_profile(wardrobe_choice: str) -> str:
    """Save the currently selected wardrobe to disk."""
    if wardrobe_choice == "Saved profile":
        existing = load_style_profile()
        if existing:
            return save_style_profile(existing)
        return "No profile loaded to re-save."
    elif wardrobe_choice == "Empty wardrobe (new user)":
        return save_style_profile(get_empty_wardrobe())
    else:
        return save_style_profile(get_example_wardrobe())


def get_wardrobe_choices() -> list[str]:
    choices = ["Example wardrobe", "Empty wardrobe (new user)"]
    if profile_exists():
        choices.insert(0, "Saved profile")
    return choices


# ── interface ─────────────────────────────────────────────────────────────────

EXAMPLE_QUERIES = [
    "vintage graphic tee under $30",
    "90s track jacket in size M",
    "flowy midi skirt under $40",
    "black combat boots size 8",
    "designer ballgown size XXS under $5",   # deliberate no-results test
]


def build_interface():
    choices = get_wardrobe_choices()
    default = "Saved profile" if profile_exists() else "Example wardrobe"

    with gr.Blocks(title="FitFindr") as demo:
        gr.Markdown("""
# FitFindr 🛍️
Find secondhand pieces and get outfit ideas based on your wardrobe.
Describe what you're looking for — include size and price if you want to filter.
        """)

        with gr.Row():
            query_input = gr.Textbox(
                label="What are you looking for?",
                placeholder="e.g. vintage graphic tee under $30, size M",
                lines=2,
                scale=3,
            )
            with gr.Column(scale=1):
                wardrobe_choice = gr.Radio(
                    choices=choices,
                    value=default,
                    label="Wardrobe",
                )
                save_btn = gr.Button("💾 Save current wardrobe", size="sm")
                save_status = gr.Textbox(label="", lines=1, interactive=False, show_label=False)

        submit_btn = gr.Button("Find it", variant="primary")

        with gr.Row():
            listing_output = gr.Textbox(
                label="🛍️ Top listing found",
                lines=10,
                interactive=False,
            )
            outfit_output = gr.Textbox(
                label="👗 Outfit idea",
                lines=10,
                interactive=False,
            )
            fitcard_output = gr.Textbox(
                label="✨ Your fit card",
                lines=10,
                interactive=False,
            )

        trending_output = gr.Textbox(
            label="🔥 Trending right now",
            lines=8,
            interactive=False,
        )

        gr.Examples(
            examples=[[q, "Example wardrobe"] for q in EXAMPLE_QUERIES],
            inputs=[query_input, wardrobe_choice],
            label="Try these queries",
        )

        # Wire submit
        submit_btn.click(
            fn=handle_query,
            inputs=[query_input, wardrobe_choice],
            outputs=[listing_output, outfit_output, fitcard_output, trending_output],
        )
        query_input.submit(
            fn=handle_query,
            inputs=[query_input, wardrobe_choice],
            outputs=[listing_output, outfit_output, fitcard_output, trending_output],
        )

        # Wire save
        save_btn.click(
            fn=handle_save_profile,
            inputs=[wardrobe_choice],
            outputs=[save_status],
        )

    return demo


if __name__ == "__main__":
    demo = build_interface()
    demo.launch()
