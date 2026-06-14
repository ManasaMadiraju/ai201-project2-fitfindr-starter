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

    trending_text = session.get("trending") or "Trend data unavailable."

    if session["error"]:
        return session["error"], "", "", trending_text

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

    if session.get("price_verdict"):
        listing_text += f"\n\n{session['price_verdict']['summary']}"

    if session.get("retry_note"):
        listing_text = f"⚠️  {session['retry_note']}\n\n" + listing_text
    if profile_note:
        listing_text = profile_note + listing_text

    return listing_text, session["outfit_suggestion"], session["fit_card"], trending_text


# ── memory handlers ───────────────────────────────────────────────────────────

def handle_save_profile(wardrobe_choice: str) -> str:
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
    "designer ballgown size XXS under $5",
]

CSS = """
body {
    background-color: #faf9f7 !important;
}

.gradio-container {
    max-width: 1200px !important;
    margin: 0 auto !important;
    font-family: 'Inter', sans-serif !important;
}

#header {
    text-align: center;
    padding: 32px 0 16px 0;
    border-bottom: 1px solid #e8e4df;
    margin-bottom: 24px;
}

#header h1 {
    font-size: 2.2rem !important;
    font-weight: 700 !important;
    color: #1a1a1a !important;
    letter-spacing: -0.5px;
}

#header p {
    color: #666 !important;
    font-size: 1rem !important;
    margin-top: 6px !important;
}

#search-row {
    background: #ffffff;
    border: 1px solid #e8e4df;
    border-radius: 12px;
    padding: 20px;
    margin-bottom: 16px;
    box-shadow: 0 1px 4px rgba(0,0,0,0.04);
}

#find-btn {
    background: #1a1a1a !important;
    color: white !important;
    border-radius: 8px !important;
    font-size: 1rem !important;
    font-weight: 600 !important;
    height: 48px !important;
    margin-bottom: 20px;
}

#find-btn:hover {
    background: #333 !important;
}

.output-panel textarea {
    background: #ffffff !important;
    border: 1px solid #e8e4df !important;
    border-radius: 10px !important;
    font-size: 0.9rem !important;
    line-height: 1.6 !important;
    color: #1a1a1a !important;
    padding: 14px !important;
}

.output-panel label {
    font-weight: 600 !important;
    font-size: 0.95rem !important;
    color: #333 !important;
    margin-bottom: 6px !important;
}

#trending-panel textarea {
    background: #fff8f0 !important;
    border: 1px solid #f0e0cc !important;
    border-radius: 10px !important;
    font-size: 0.9rem !important;
    color: #1a1a1a !important;
}

#save-btn {
    background: #f5f5f5 !important;
    color: #333 !important;
    border: 1px solid #ddd !important;
    border-radius: 8px !important;
    font-size: 0.85rem !important;
}

#save-status textarea {
    font-size: 0.8rem !important;
    color: #555 !important;
    border: none !important;
    background: transparent !important;
    padding: 4px 0 !important;
}

.gr-examples {
    margin-top: 8px;
}
"""


def build_interface():
    choices = get_wardrobe_choices()
    default = "Saved profile" if profile_exists() else "Example wardrobe"

    with gr.Blocks(title="FitFindr", css=CSS, theme=gr.themes.Default(
        font=gr.themes.GoogleFont("Inter"),
        primary_hue="neutral",
        neutral_hue="slate",
    )) as demo:

        with gr.Column(elem_id="header"):
            gr.Markdown("""
# FitFindr 🛍️
Find secondhand pieces and get outfit ideas based on your wardrobe.
            """)

        with gr.Row(elem_id="search-row"):
            query_input = gr.Textbox(
                label="What are you looking for?",
                placeholder="e.g. vintage graphic tee under $30, size M",
                lines=2,
                scale=4,
                container=True,
            )
            with gr.Column(scale=1, min_width=200):
                wardrobe_choice = gr.Radio(
                    choices=choices,
                    value=default,
                    label="Wardrobe",
                )
                save_btn = gr.Button("💾 Save wardrobe", size="sm", elem_id="save-btn")
                save_status = gr.Textbox(
                    label="",
                    lines=1,
                    interactive=False,
                    show_label=False,
                    elem_id="save-status",
                )

        submit_btn = gr.Button("🔍 Find it", variant="primary", elem_id="find-btn")

        with gr.Row():
            listing_output = gr.Textbox(
                label="🛍️ Top Listing",
                lines=12,
                interactive=False,
                elem_classes="output-panel",
            )
            outfit_output = gr.Textbox(
                label="👗 Outfit Idea",
                lines=12,
                interactive=False,
                elem_classes="output-panel",
            )
            fitcard_output = gr.Textbox(
                label="✨ Fit Card Caption",
                lines=12,
                interactive=False,
                elem_classes="output-panel",
            )

        trending_output = gr.Textbox(
            label="🔥 Trending Right Now",
            lines=6,
            interactive=False,
            elem_id="trending-panel",
            elem_classes="output-panel",
        )

        gr.Examples(
            examples=[[q, "Example wardrobe"] for q in EXAMPLE_QUERIES],
            inputs=[query_input, wardrobe_choice],
            label="Try these",
        )

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

        save_btn.click(
            fn=handle_save_profile,
            inputs=[wardrobe_choice],
            outputs=[save_status],
        )

    return demo


if __name__ == "__main__":
    demo = build_interface()
    demo.launch()
