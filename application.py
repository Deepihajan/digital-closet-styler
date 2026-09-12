"""
Split-Second Wardrobe Outfit Styler
===================================

A Streamlit app that picks outfits from your own wardrobe in under a second.

You tell it the occasion, the temperature and the vibe you're after; it scores
every valid combination of top / bottom / footwear (+ optional outerwear and
accessory) on formality fit, warmth fit, colour harmony and pattern balance,
then shows you the best few.

Run it
------
    pip install streamlit
    streamlit run outfit_styler.py

Your wardrobe is saved to `wardrobe.json` next to this file, so edits survive
restarts. Delete that file to go back to the seed wardrobe.

Tested on Streamlit >= 1.32 (uses st.container(border=True)).
"""

from __future__ import annotations

import colorsys
import itertools
import json
import random
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path

import streamlit as st

# --------------------------------------------------------------------------
# Reference data
# --------------------------------------------------------------------------

DATA_FILE = Path(__file__).resolve().parent / "wardrobe.json"

CATEGORIES = ["Top", "Bottom", "Outerwear", "Footwear", "Accessory"]
PATTERNS = ["Solid", "Striped", "Checked", "Printed", "Textured"]

COLOR_HEX = {
    "White": "#FFFFFF",
    "Off-white": "#F3EEE4",
    "Cream": "#F5E7CC",
    "Beige": "#D9C4A3",
    "Khaki": "#BCB18D",
    "Grey": "#909499",
    "Charcoal": "#3A3E44",
    "Black": "#16181B",
    "Navy": "#1F2C49",
    "Denim": "#42648F",
    "Blue": "#2E6BD6",
    "Sky": "#8FC1EE",
    "Teal": "#1B7B75",
    "Green": "#2F7A3E",
    "Olive": "#5D6B3A",
    "Mustard": "#C8962B",
    "Yellow": "#E6C24C",
    "Orange": "#DD7A2C",
    "Rust": "#A44E27",
    "Red": "#BF3A2D",
    "Maroon": "#6D2333",
    "Pink": "#E49FB3",
    "Lavender": "#A99AD1",
    "Purple": "#6A4E9B",
    "Brown": "#6A4A2F",
    "Tan": "#B08355",
}

# Colours that sit quietly beside anything else.
NEUTRALS = {
    "White", "Off-white", "Cream", "Beige", "Khaki", "Grey",
    "Charcoal", "Black", "Navy", "Denim", "Brown", "Tan",
}

EARTHY = {"Olive", "Rust", "Brown", "Tan", "Beige", "Khaki", "Mustard", "Cream", "Maroon"}

# occasion -> (target formality 1-5, short note shown in the UI)
OCCASIONS = {
    "Around the house": (1, "comfort first, nobody is looking"),
    "Errands / coffee run": (2, "casual but put together"),
    "Work from office": (4, "clean lines, low drama"),
    "Client meeting": (5, "the room should trust you"),
    "Smart casual dinner": (3, "relaxed, still considered"),
    "Wedding / function": (5, "dress up, commit to it"),
    "Temple visit": (4, "modest, covered, respectful"),
    "Travel day": (2, "layers you can shed on a plane"),
    "Gym / active": (1, "movement over everything"),
}

VIBES = ["Balanced", "Tonal", "Bold contrast", "Earthy", "Minimal"]

MAX_COMBINATIONS = 6000  # sampling cap so the app stays "split-second"


# --------------------------------------------------------------------------
# Item model
# --------------------------------------------------------------------------

@dataclass
class Item:
    name: str
    category: str
    color: str
    formality: int = 3        # 1 = pyjamas, 5 = black tie
    warmth: int = 3           # 1 = mesh vest, 5 = parka
    pattern: str = "Solid"
    tags: list[str] = field(default_factory=list)
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])

    @property
    def hex(self) -> str:
        return COLOR_HEX.get(self.color, "#888888")


def seed_wardrobe() -> list[Item]:
    """A starter wardrobe so the app is useful on first launch."""
    raw = [
        # Tops
        ("White oxford shirt",      "Top", "White",     4, 2, "Solid",    ["shirt"]),
        ("Sky blue formal shirt",   "Top", "Sky",       5, 2, "Solid",    ["shirt"]),
        ("Navy polo",               "Top", "Navy",      3, 2, "Solid",    []),
        ("Grey crew tee",           "Top", "Grey",      1, 1, "Solid",    ["tee"]),
        ("Black tee",               "Top", "Black",     2, 1, "Solid",    ["tee"]),
        ("Olive linen shirt",       "Top", "Olive",     3, 1, "Textured", ["linen"]),
        ("Maroon striped shirt",    "Top", "Maroon",    3, 2, "Striped",  []),
        ("Cream kurta",             "Top", "Cream",     4, 2, "Solid",    ["ethnic"]),
        ("Charcoal merino sweater", "Top", "Charcoal",  4, 4, "Solid",    ["knit"]),
        # Bottoms
        ("Indigo jeans",            "Bottom", "Denim",    2, 3, "Solid",   ["jeans"]),
        ("Black jeans",             "Bottom", "Black",    3, 3, "Solid",   ["jeans"]),
        ("Beige chinos",            "Bottom", "Beige",    3, 2, "Solid",   ["chinos"]),
        ("Navy chinos",             "Bottom", "Navy",     4, 2, "Solid",   ["chinos"]),
        ("Charcoal trousers",       "Bottom", "Charcoal", 5, 3, "Solid",   ["formal"]),
        ("Grey joggers",            "Bottom", "Grey",     1, 2, "Solid",   ["active"]),
        ("Olive cargo shorts",      "Bottom", "Olive",    1, 1, "Solid",   ["shorts"]),
        # Outerwear
        ("Navy blazer",             "Outerwear", "Navy",    5, 3, "Solid",   ["blazer"]),
        ("Denim jacket",            "Outerwear", "Denim",   2, 3, "Solid",   []),
        ("Black puffer",            "Outerwear", "Black",   2, 5, "Solid",   ["winter"]),
        # Footwear
        ("White sneakers",          "Footwear", "White",    2, 2, "Solid",  ["sneakers"]),
        ("Brown leather derbies",   "Footwear", "Brown",    5, 3, "Solid",  ["formal"]),
        ("Black loafers",           "Footwear", "Black",    4, 3, "Solid",  []),
        ("Running shoes",           "Footwear", "Grey",     1, 2, "Solid",  ["active"]),
        ("Tan sandals",             "Footwear", "Tan",      1, 1, "Solid",  ["summer"]),
        # Accessories
        ("Brown leather belt",      "Accessory", "Brown",   4, 1, "Solid",  ["belt"]),
        ("Steel watch",             "Accessory", "Grey",    4, 1, "Solid",  ["watch"]),
        ("Mustard scarf",           "Accessory", "Mustard", 3, 3, "Solid",  ["winter"]),
        ("Black cap",               "Accessory", "Black",   1, 1, "Solid",  []),
    ]
    return [
        Item(name=n, category=c, color=col, formality=f, warmth=w, pattern=p, tags=t)
        for n, c, col, f, w, p, t in raw
    ]


# --------------------------------------------------------------------------
# Persistence
# --------------------------------------------------------------------------

def load_wardrobe() -> list[Item]:
    if DATA_FILE.exists():
        try:
            rows = json.loads(DATA_FILE.read_text(encoding="utf-8"))
            return [Item(**r) for r in rows]
        except (json.JSONDecodeError, TypeError, ValueError):
            st.warning("wardrobe.json couldn't be read, so the seed wardrobe was loaded instead.")
    return seed_wardrobe()


def save_wardrobe(items: list[Item]) -> None:
    DATA_FILE.write_text(
        json.dumps([asdict(i) for i in items], indent=2),
        encoding="utf-8",
    )


# --------------------------------------------------------------------------
# Colour maths
# --------------------------------------------------------------------------

def to_hsv(hex_code: str) -> tuple[float, float, float]:
    hex_code = hex_code.lstrip("#")
    r, g, b = (int(hex_code[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return colorsys.rgb_to_hsv(r, g, b)


def hue_gap(h1: float, h2: float) -> float:
    """Distance around the colour wheel, 0.0 (same) to 0.5 (opposite)."""
    d = abs(h1 - h2) % 1.0
    return min(d, 1.0 - d)


def pair_harmony(c1: str, c2: str) -> float:
    """How well two named colours sit together. 0.0 - 1.0."""
    n1, n2 = c1 in NEUTRALS, c2 in NEUTRALS

    if n1 and n2:
        v1, v2 = to_hsv(COLOR_HEX[c1])[2], to_hsv(COLOR_HEX[c2])[2]
        # Neutrals always work; a little separation in brightness works better.
        return 0.80 + min(abs(v1 - v2), 0.4) * 0.4
    if n1 or n2:
        return 0.95  # one neutral anchors any colour

    h1, s1, _ = to_hsv(COLOR_HEX[c1])
    h2, s2, _ = to_hsv(COLOR_HEX[c2])
    gap = hue_gap(h1, h2)
    loud = (s1 + s2) / 2  # two saturated colours fight harder

    if gap < 0.05:
        return 0.90                              # monochrome
    if gap < 0.17:
        return 0.86                              # analogous
    if gap > 0.40:
        return 0.78 - 0.15 * loud                # complementary, needs nerve
    return 0.40 - 0.15 * loud                    # awkward middle distance


def outfit_harmony(items: list[Item]) -> float:
    """Average pairwise harmony, with accessories counting for less."""
    weighted = []
    for a, b in itertools.combinations(items, 2):
        w = 0.5 if "Accessory" in (a.category, b.category) else 1.0
        weighted.append((pair_harmony(a.color, b.color), w))
    if not weighted:
        return 1.0
    total_w = sum(w for _, w in weighted)
    return sum(s * w for s, w in weighted) / total_w


def readable_on(hex_code: str) -> str:
    """Pick black or white text for a swatch background."""
    _, _, v = to_hsv(hex_code)
    return "#16181B" if v > 0.62 else "#FFFFFF"


# --------------------------------------------------------------------------
# Scoring
# --------------------------------------------------------------------------

def warmth_target(temp_c: float) -> float:
    """Map temperature to a 1-5 warmth need."""
    if temp_c >= 32:
        return 1.0
    if temp_c >= 27:
        return 1.5
    if temp_c >= 22:
        return 2.0
    if temp_c >= 17:
        return 2.7
    if temp_c >= 12:
        return 3.4
    if temp_c >= 6:
        return 4.2
    return 5.0


def score_outfit(
    items: list[Item],
    target_form: float,
    target_warm: float,
    vibe: str,
    rain: bool,
) -> tuple[float, dict[str, float]]:
    core = [i for i in items if i.category != "Accessory"]

    # 1. Formality — the mean should land on target, and the spread should be
    #    small (no running shoes under a blazer).
    forms = [i.formality for i in core]
    mean_form = sum(forms) / len(forms)
    spread = max(forms) - min(forms)
    form_score = max(0.0, 1 - abs(mean_form - target_form) / 2.5) * max(0.35, 1 - spread * 0.18)

    # 2. Warmth — total insulation against what the weather asks for.
    warm = sum(i.warmth for i in core) / len(core)
    if items and any(i.category == "Outerwear" for i in items):
        warm += 0.6
    warm_score = max(0.0, 1 - abs(warm - target_warm) / 2.5)
    # A scarf in 34 degrees is not a styling choice, it's a mistake.
    for i in items:
        if i.category == "Accessory" and i.warmth >= 3 and target_warm < 2.5:
            warm_score *= 0.45

    # 3. Colour.
    color_score = outfit_harmony(items)

    # 4. Pattern — one statement piece, not three.
    patterned = sum(1 for i in items if i.pattern not in ("Solid", "Textured"))
    pattern_score = {0: 0.92, 1: 1.0, 2: 0.55}.get(patterned, 0.25)

    # 5. Vibe.
    colors = [i.color for i in core]
    chromatic = [c for c in colors if c not in NEUTRALS]
    vibe_score = 0.7
    if vibe == "Tonal":
        vibe_score = 1.0 if len(set(colors)) <= 2 or not chromatic else 0.55
    elif vibe == "Bold contrast":
        if len(chromatic) >= 2:
            hues = [to_hsv(COLOR_HEX[c])[0] for c in chromatic]
            vibe_score = 0.5 + max(hue_gap(a, b) for a, b in itertools.combinations(hues, 2))
        else:
            vibe_score = 0.55 if chromatic else 0.4
    elif vibe == "Earthy":
        vibe_score = 0.4 + 0.6 * (sum(1 for c in colors if c in EARTHY) / len(colors))
    elif vibe == "Minimal":
        vibe_score = (1.0 if patterned == 0 else 0.5) * (1.0 if len(set(colors)) <= 3 else 0.7)
    else:  # Balanced
        vibe_score = 0.85

    # 6. Rain nudge: sandals and canvas are a bad idea.
    rain_penalty = 0.0
    if rain:
        for i in items:
            if i.category == "Footwear" and {"summer", "sneakers"} & set(i.tags):
                rain_penalty = 0.12
        if not any(i.category == "Outerwear" for i in items):
            rain_penalty += 0.08

    weights = {
        "Occasion fit": (form_score, 0.34),
        "Weather fit": (warm_score, 0.24),
        "Colour": (color_score, 0.26),
        "Pattern": (pattern_score, 0.08),
        "Vibe": (min(vibe_score, 1.0), 0.08),
    }
    total = sum(s * w for s, w in weights.values()) - rain_penalty
    breakdown = {k: round(s * 100) for k, (s, _) in weights.items()}
    return max(0.0, min(1.0, total)) * 100, breakdown


# --------------------------------------------------------------------------
# Outfit generation
# --------------------------------------------------------------------------

def by_category(wardrobe: list[Item], cat: str, locked_id: str | None) -> list[Item]:
    items = [i for i in wardrobe if i.category == cat]
    if locked_id:
        pinned = [i for i in items if i.id == locked_id]
        if pinned:
            return pinned
    return items


def build_outfits(
    wardrobe: list[Item],
    occasion: str,
    temp_c: float,
    vibe: str,
    rain: bool,
    locks: dict[str, str | None],
    how_many: int,
    nonce: int,
):
    target_form = OCCASIONS[occasion][0]
    target_warm = warmth_target(temp_c)
    rng = random.Random(nonce)

    tops = by_category(wardrobe, "Top", locks.get("Top"))
    bottoms = by_category(wardrobe, "Bottom", locks.get("Bottom"))
    shoes = by_category(wardrobe, "Footwear", locks.get("Footwear"))
    if not (tops and bottoms and shoes):
        return [], "You need at least one top, one bottom and one pair of shoes."

    outer = by_category(wardrobe, "Outerwear", locks.get("Outerwear"))
    accs = by_category(wardrobe, "Accessory", locks.get("Accessory"))

    # Outerwear is optional unless it's cold, raining, or the user pinned one.
    outer_opts: list[Item | None] = list(outer)
    if not locks.get("Outerwear") and not (temp_c < 18 or rain):
        outer_opts = [None] + outer_opts
    elif not locks.get("Outerwear"):
        outer_opts = outer_opts + [None]
    if not outer_opts:
        outer_opts = [None]

    acc_opts: list[Item | None] = list(accs)
    if not locks.get("Accessory"):
        acc_opts = [None] + acc_opts
    if not acc_opts:
        acc_opts = [None]

    combos = itertools.product(tops, bottoms, shoes, outer_opts, acc_opts)
    total = len(tops) * len(bottoms) * len(shoes) * len(outer_opts) * len(acc_opts)
    if total > MAX_COMBINATIONS:
        combos = rng.sample(list(combos), MAX_COMBINATIONS)

    scored = []
    for combo in combos:
        items = [i for i in combo if i is not None]
        score, breakdown = score_outfit(items, target_form, target_warm, vibe, rain)
        scored.append((score + rng.random() * 0.4, score, items, breakdown))

    scored.sort(key=lambda r: r[0], reverse=True)

    # Keep the results visibly different from one another.
    picked, seen_pairs = [], {}
    for _, score, items, breakdown in scored:
        key = tuple(sorted(i.id for i in items if i.category in ("Top", "Bottom")))
        if seen_pairs.get(key, 0) >= 1:
            continue
        seen_pairs[key] = seen_pairs.get(key, 0) + 1
        picked.append((score, items, breakdown))
        if len(picked) >= how_many:
            break
    return picked, None


# --------------------------------------------------------------------------
# UI
# --------------------------------------------------------------------------

st.set_page_config(page_title="Split-Second Wardrobe", page_icon="👔", layout="wide")

st.markdown(
    """
    <style>
      .swatch-row { display: flex; gap: 6px; flex-wrap: wrap; margin: 2px 0 10px 0; }
      .swatch {
        border-radius: 3px; padding: 5px 11px; font-size: 0.78rem;
        letter-spacing: 0.01em; border: 1px solid rgba(0,0,0,0.18);
        white-space: nowrap;
      }
      .piece { font-size: 0.93rem; line-height: 1.65; }
      .piece-cat { opacity: 0.55; display: inline-block; min-width: 82px; }
    </style>
    """,
    unsafe_allow_html=True,
)

if "wardrobe" not in st.session_state:
    st.session_state.wardrobe = load_wardrobe()
if "nonce" not in st.session_state:
    st.session_state.nonce = 1

wardrobe: list[Item] = st.session_state.wardrobe


def lock_picker(cat: str) -> str | None:
    """Let the user pin one garment so every suggestion includes it."""
    opts = [i for i in wardrobe if i.category == cat]
    if not opts:
        return None
    labels = ["Anything"] + [i.name for i in opts]
    choice = st.selectbox(cat, labels, key=f"lock_{cat}")
    return None if choice == "Anything" else next(i.id for i in opts if i.name == choice)


with st.sidebar:
    st.header("Today")
    occasion = st.selectbox("Where are you going?", list(OCCASIONS))
    st.caption(OCCASIONS[occasion][1])
    temp_c = st.slider("Temperature (°C)", -5, 45, 30)
    rain = st.checkbox("Rain expected")
    vibe = st.radio("Vibe", VIBES, horizontal=False)
    how_many = st.slider("Outfits to show", 1, 6, 3)

    st.divider()
    st.subheader("Build around a piece")
    st.caption("Pin something you already want to wear.")
    locks = {cat: lock_picker(cat) for cat in CATEGORIES}

    if st.button("Style me", type="primary", use_container_width=True):
        st.session_state.nonce += 1
    st.caption("Press again for a different set.")


tab_style, tab_wardrobe, tab_add = st.tabs(["Style me", "Wardrobe", "Add a piece"])


with tab_style:
    st.title("What to wear")
    outfits, problem = build_outfits(
        wardrobe, occasion, temp_c, vibe, rain, locks, how_many, st.session_state.nonce
    )

    if problem:
        st.info(problem)
    else:
        for rank, (score, items, breakdown) in enumerate(outfits, start=1):
            with st.container(border=True):
                left, right = st.columns([3, 1])

                with left:
                    st.markdown(f"**Option {rank}**")
                    swatches = "".join(
                        f'<span class="swatch" style="background:{i.hex};'
                        f'color:{readable_on(i.hex)}">{i.color}</span>'
                        for i in items
                    )
                    st.markdown(f'<div class="swatch-row">{swatches}</div>', unsafe_allow_html=True)

                    order = {c: n for n, c in enumerate(CATEGORIES)}
                    lines = "".join(
                        f'<div class="piece"><span class="piece-cat">{i.category}</span>'
                        f'{i.name}'
                        + (f' · {i.pattern.lower()}' if i.pattern != "Solid" else "")
                        + "</div>"
                        for i in sorted(items, key=lambda x: order[x.category])
                    )
                    st.markdown(lines, unsafe_allow_html=True)

                with right:
                    st.metric("Match", f"{score:.0f}")
                    st.progress(min(score / 100, 1.0))
                    with st.popover("Why this works"):
                        for label, value in breakdown.items():
                            st.write(f"{label}: {value}")


with tab_wardrobe:
    st.title("Wardrobe")
    st.caption(f"{len(wardrobe)} pieces. Saved to {DATA_FILE.name}.")

    for cat in CATEGORIES:
        rows = [i for i in wardrobe if i.category == cat]
        if not rows:
            continue
        st.subheader(f"{cat}  ·  {len(rows)}")
        for item in rows:
            c1, c2, c3, c4 = st.columns([4, 3, 3, 1])
            c1.markdown(
                f'<span class="swatch" style="background:{item.hex};'
                f'color:{readable_on(item.hex)}">&nbsp;</span>&nbsp; {item.name}',
                unsafe_allow_html=True,
            )
            c2.caption(f"{item.color} · {item.pattern.lower()}")
            c3.caption(f"formality {item.formality} · warmth {item.warmth}")
            if c4.button("Remove", key=f"del_{item.id}"):
                st.session_state.wardrobe = [i for i in wardrobe if i.id != item.id]
                save_wardrobe(st.session_state.wardrobe)
                st.rerun()

    st.divider()
    if st.button("Reset to the starter wardrobe"):
        st.session_state.wardrobe = seed_wardrobe()
        save_wardrobe(st.session_state.wardrobe)
        st.rerun()


with tab_add:
    st.title("Add a piece")
    with st.form("add_item", clear_on_submit=True):
        c1, c2 = st.columns(2)
        name = c1.text_input("Name", placeholder="Olive linen shirt")
        category = c2.selectbox("Category", CATEGORIES)
        color = c1.selectbox("Colour", list(COLOR_HEX))
        pattern = c2.selectbox("Pattern", PATTERNS)
        formality = c1.slider("Formality", 1, 5, 3, help="1 is loungewear, 5 is black tie")
        warmth = c2.slider("Warmth", 1, 5, 2, help="1 is barely there, 5 is a winter coat")
        tags = st.text_input("Tags", placeholder="linen, summer", help="Comma separated, optional")

        if st.form_submit_button("Add to wardrobe", type="primary"):
            if not name.strip():
                st.error("Give the piece a name so you can recognise it later.")
            else:
                st.session_state.wardrobe.append(
                    Item(
                        name=name.strip(),
                        category=category,
                        color=color,
                        formality=formality,
                        warmth=warmth,
                        pattern=pattern,
                        tags=[t.strip() for t in tags.split(",") if t.strip()],
                    )
                )
                save_wardrobe(st.session_state.wardrobe)
                st.success(f"{name.strip()} is in the wardrobe.")