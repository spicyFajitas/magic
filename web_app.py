import os
import io
import zipfile

import streamlit as st
import pandas as pd
import altair as alt

from edhrec_backend import EDHRecAnalyzer

analyzer = EDHRecAnalyzer()

###################################
# Streamlit UI Setup
###################################

st.set_page_config(
    page_title="EDHRec Deck Builder Tool",
    layout="centered",
    menu_items={
        "Get help": "https://github.com/spicyFajitas/edhrec-deck-building-scripts/issues",
        "Report a bug": "https://github.com/spicyFajitas/edhrec-deck-building-scripts/issues",
        "About": (
            "🧙‍♂️ EDHRec Deck Builder Tool\n\n"
            "Build Commander decks using EDHREC data.\n\n"
            "GitHub: https://github.com/spicyFajitas/edhrec-deck-building-scripts"
        ),
    },
)
st.title("🧙‍♂️ EDHRec Deck Builder Tool")
st.write("Fetch, analyze, and categorize EDHREC decklists automatically.")
st.write(
    "This tool aggregates data from EDHRec for a given commander and shows the commonly used cards in a deck by count of how many decks the card is in."
)

# ✅ NEW: tiny CSS for hover previews (optional but nice)
st.markdown("""
<style>
.card-hover {
    position: relative;
    display: block;
    width: max-content;
    margin: 6px 0;
    padding: 2px 0;
    cursor: pointer;
    white-space: nowrap;
}

/* Preview container */
.card-hover img {
    display: none;
    position: absolute;
    left: 110%;
    top: 0;

    width: 280px;
    aspect-ratio: 5 / 7;
    object-fit: contain;

    transform: translateY(-60%) scale(1.3);
    transform-origin: top left;

    z-index: 1000;
    border-radius: 12px;
    box-shadow: 0 14px 32px rgba(0,0,0,0.65);
    background: #111;
}


/* Show on hover */
.card-hover:hover img {
    display: block;
}
</style>
""", unsafe_allow_html=True)



###################################
# Session State Initialization
###################################

defaults = {
    "results_ready": False,
    "output_dir": None,
    "formatted_name": None,
    "commander_name": None,
    "recent": None,
    "min_price": None,
    "max_price": None,
    "deck_hashes": None,
    "all_decks": None,
    "card_counts": None,
    "type_groups": None,
    "final_status": None,
}

for key, value in defaults.items():
    st.session_state.setdefault(key, value)

###################################
# Inputs
###################################

st.header("Commander Selection")

commander_name = st.text_input(
    "Commander Name",
    # value=default_commander,
    placeholder="e.g. Atraxa, Praetors' Voice"
)

st.header("Deck Query Filters")
recent = st.number_input("How many recent decks to fetch?", 5, 200, 20, 5)
min_price = st.number_input("Minimum deck price", 5, 10000, 5, 5)
max_price = st.number_input("Maximum deck price", 5, 10000, 100, 5)

run_button = st.button("Fetch & Analyze Decklists")

if not st.session_state.results_ready and not run_button:
    st.info("Ready when you are — enter your commander and press the button!")

final_status_box = st.empty()


###################################
# Run
###################################

if run_button:
    st.session_state.results_ready = False

    if not commander_name.strip():
        st.warning("Enter a commander name first.")
        st.stop()

    active_step = st.empty()   # ⭐ SINGLE ACTIVE STEP SLOT

    formatted_name = analyzer.format_commander_name(commander_name)

    st.session_state.update(
        commander_name=commander_name,
        formatted_name=formatted_name,
        recent=int(recent),
        min_price=float(min_price),
        max_price=float(max_price),
    )

    try:
        # Step 1 — Build ID
        active_step.info("🔄 Detecting EDHREC build ID…")
        build_id = analyzer.fetch_edhrec_build_id()

        if not formatted_name or "-" not in formatted_name:
            st.warning(
                "Commander name looks incomplete.\n\n"
                "Use the full card name, e.g. *Atraxa, Praetors' Voice*"
            )


        # Step 2 — Deck Table
        active_step.info("🔄 Fetching deck table…")

        try:
            deck_table = analyzer.fetch_deck_table(formatted_name)
        except Exception:
            active_step.empty()
            st.error(
                f"❌ Commander **{commander_name}** was not found on EDHREC.\n\n"
                "Please check:\n"
                "- spelling\n"
                "- punctuation\n"
                "- full card name (no nicknames)\n\n"
                "Example: *Atraxa, Praetors' Voice*"
            )
            st.stop()


        deck_hashes = analyzer.filter_deck_hashes(
            deck_table,
            int(recent),
            float(min_price),
            float(max_price),
        )
        st.session_state.deck_hashes = deck_hashes

        if not deck_hashes:
            active_step.empty()
            st.warning(
                f"⚠️ **{commander_name}** was found, but no decks matched your filters.\n\n"
                "Try:\n"
                "- increasing the number of recent decks\n"
                "- widening the price range\n"
                "- removing the minimum price filter"
            )
            st.stop()


        # Step 3 — Download Decklists
        active_step.info("🔄 Downloading decklists…")
        progress = st.progress(0)
        status = st.empty()

        all_decks = []
        for completed, total, deck in analyzer.fetch_decks_with_progress(deck_hashes):
            if deck:
                all_decks.append(deck)
            progress.progress(completed / total)
            status.info(f"Downloaded {completed}/{total} decks")

        progress.empty()
        status.empty()

        st.session_state.all_decks = all_decks

        # Step 4 — Write Output Files
        active_step.info("🔄 Writing output files…")

        output_dir = analyzer.clean_output_directories(formatted_name)
        st.session_state.output_dir = output_dir

        metadata_header = analyzer.build_metadata_header(
            commander_name,
            int(recent),
            float(min_price),
            float(max_price),
            source_info={"streamlit-ui": True},
        )

        analyzer.save_decklists(all_decks, output_dir, formatted_name, metadata_header)

        # Step 5 — Count Cards
        active_step.info("🔄 Counting cards…")
        card_counts = analyzer.count_cards(all_decks)
        st.session_state.card_counts = card_counts

        analyzer.save_master_cardcount(card_counts, output_dir, metadata_header)

        # Step 6 — Classify Cards
        active_step.info("🔄 Classifying cards by type…")
        type_progress = st.progress(0)
        type_status = st.empty()

        type_groups = {
            "Creature": {},
            "Instant": {},
            "Sorcery": {},
            "Artifact": {},
            "Enchantment": {},
            "Planeswalker": {},
            "Battle": {},
            "Land": {},
            "Unknown": {},
        }

        items = list(card_counts.items())
        total_cards = len(items)

        for idx, (card, count) in enumerate(items, start=1):
            type_line = analyzer.get_card_type(card)
            matched = False

            for t in type_groups:
                if t != "Unknown" and t in type_line:
                    type_groups[t][card] = count
                    matched = True
                    break

            if not matched:
                type_groups["Unknown"][card] = count

            type_progress.progress(idx / total_cards)
            type_status.info(f"Classified {idx}/{total_cards} cards")

        type_progress.empty()
        type_status.empty()
        active_step.empty()

        st.session_state.type_groups = type_groups
        analyzer.save_cardtypes(type_groups, output_dir, metadata_header)

        # Done
        st.session_state.final_status = "success"
        st.session_state.results_ready = True


    except Exception as e:
        st.session_state.final_status = "error"
        final_status_box.error(f"❌ Error: {e}")
        st.stop()


if st.session_state.final_status == "success":
    final_status_box.success("✅ Processing complete!")
elif st.session_state.final_status == "error":
    final_status_box.error("❌ Processing failed.")


###################################
# Results (Tabbed UX)
###################################

if st.session_state.results_ready:
    output_dir = st.session_state.output_dir
    formatted_name = st.session_state.formatted_name
    card_counts = st.session_state.card_counts
    type_groups = st.session_state.type_groups

    BASIC_LANDS = {
        "Plains", "Island", "Swamp", "Mountain", "Forest"
    }

    filtered_card_counts = {
    card: count
    for card, count in card_counts.items()
    if card not in BASIC_LANDS
    }

    filtered_type_groups = {
        type_name: {
            card: count
            for card, count in cards.items()
            if card not in BASIC_LANDS
        }
        for type_name, cards in type_groups.items()
    }

    show_basics = st.checkbox("Include basic lands", value=False)

    active_card_counts = card_counts if show_basics else filtered_card_counts
    active_type_groups = type_groups if show_basics else filtered_type_groups


    # -------------------------------
    # Prepare files once
    # -------------------------------
    output_files = sorted(
        fn for fn in os.listdir(output_dir)
        if os.path.isfile(os.path.join(output_dir, fn))
    )

    file_data = {
        fn: open(os.path.join(output_dir, fn), "rb").read()
        for fn in output_files
    }

    # -------------------------------
    # Tabs
    # -------------------------------
    active_tab = st.radio(
    "View",
    ["📊 Dashboard", "🖼️ Cards", "📄 Files", "📦 Download"],
    horizontal=True,
    key="active_tab"
    )

    # ============================================================
    # DASHBOARD TAB
    # ============================================================
    if active_tab == "📊 Dashboard":
        st.subheader("Card Analysis Dashboard")

        card_df = pd.DataFrame(
            active_card_counts.items(),
            columns=["Card", "Count"]
        ).sort_values("Count", ascending=False)

        top_n = st.slider(
            "Show top N cards",
            min_value=5,
            max_value=100,
            value=20,
            key="dashboard_top_n"
        )

        rows = len(card_df.head(top_n))
        dynamic_height = min(max(rows * 24, 200), 1200)

        chart = (
            alt.Chart(card_df.head(top_n))
            .mark_bar()
            .encode(
                x=alt.X("Count:Q", title="Frequency Across Decks"),
                #y=alt.Y("Card:N", sort="-x", title="Card Name"), # Vega-Lite has an automatic label de-overlap algorithm on categorical axes
                y=alt.Y(
                    "Card:N",
                    sort="-x",
                    title="Card Name",
                    axis=alt.Axis(
                        labelOverlap=False,   # 🔥 CRITICAL: stop Vega from skipping labels
                        labelFontSize=11,
                    ),
                ),
                tooltip=["Card", "Count"]
            )
            .properties(height=dynamic_height)
        )

        st.altair_chart(chart, use_container_width=True)

    # ============================================================
    # CARDS TAB
    # ============================================================
    if active_tab == "🖼️ Cards":
        st.subheader("Visual Card Browser")

        preview_file = st.selectbox(
            "Select a card list to visualize",
            options=["(none)"] + output_files,
            key="cards_preview_file"
        )

        show_images = st.checkbox("Show card images", value=True)
        max_cards = st.slider(
            "Max cards to render",
            min_value=10,
            max_value=120,
            value=40,
            step=10
        )

        def cards_for_file(filename):
            if filename == "master_card_counts.txt":
                return active_card_counts
            if filename.startswith("cards_") and filename.endswith(".txt"):
                type_name = filename.replace("cards_", "").replace(".txt", "").capitalize()
                return active_type_groups.get(type_name, {})
            return None


        selected_cards = cards_for_file(preview_file)

        if show_images and selected_cards:
            sorted_cards = sorted(
                selected_cards.items(),
                key=lambda x: x[1],
                reverse=True
            )[:max_cards]

            for card, count in sorted_cards:
                meta = analyzer.get_card_metadata(card)
                img = meta.get("image_url")
                url = meta.get("scryfall_uri") or "#"

                if img:
                    st.markdown(
                        f"""
                        <div class="card-hover">
                            <b>{count}×</b> <a href="{url}" target="_blank">{card}</a>
                            <img src="{img}" />
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
                else:
                    st.markdown(f"**{count}×** [{card}]({url})")

        elif preview_file != "(none)":
            st.info("Select a master list or card type file to display images.")

    # ============================================================
    # FILES TAB
    # ============================================================
    if active_tab == "📄 Files":
        st.subheader("Raw Output Files")

        preview_file = st.selectbox(
            "Choose a file to preview",
            options=["(none)"] + output_files,
            key="files_preview_file"
        )

        if preview_file != "(none)":
            try:
                st.code(file_data[preview_file].decode("utf-8"), language="text")
            except Exception:
                st.warning("Cannot display this file as text.")

        st.subheader("Download individual files")

        selected_files = st.multiselect(
            "Select files",
            options=output_files,
            default=[]
        )

        for filename in selected_files:
            st.download_button(
                label=f"⬇ Download {filename}",
                data=file_data[filename],
                file_name=filename,
                mime="text/plain"
            )

    # ============================================================
    # DOWNLOAD TAB
    # ============================================================
    if active_tab == "📦 Download":
        st.subheader("Download All Outputs")

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zipf:
            for fn, data in file_data.items():
                zipf.writestr(fn, data)

        st.download_button(
            "📦 Download All as ZIP",
            zip_buffer.getvalue(),
            f"{formatted_name}_edhrec_output.zip",
            "application/zip",
        )
