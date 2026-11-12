"""All Else Equal chart style: grey first, one thing in Mulberry.

Typical use:

    from mmm_ground_truth.style import (INK, MULBERRY, add_source, apply_style, highlight,
                                       takeaway_title)

    apply_style()
    fig, ax = plt.subplots(figsize=(9, 5.2))
    fig.subplots_adjust(top=0.74)                 # leave room for the title block
    ax.barh(names, values, color=highlight(names, "Paid search"))
    takeaway_title(fig, [[("Paid search", MULBERRY), (" accounts for a third of", INK)],
                         [("modeled incremental revenue", INK)]],
                   subtitle="Share by channel (modeled)")
    add_source(fig, "Source: ...")

Fonts: Source Serif 4 (titles) and Source Sans 3 (text) when installed, otherwise Georgia /
Segoe UI / DejaVu. Install the two Google Fonts for the exact brand look.
"""

import matplotlib.pyplot as plt
from matplotlib import font_manager

MULBERRY = "#8C2552"
INK = "#1F2430"
SLATE = "#4B5563"
LABEL = "#6B7280"
MID = "#9CA3AF"
LIGHT = "#D1D5DB"
MIST = "#F4F5F7"
TEAL = "#1F7A6E"
AMBER = "#C9821B"
AMBER_TEXT = "#9A6210"


def _first_available(candidates: list[str]) -> str:
    """First installed font from the list (avoids matplotlib's findfont warning spam)."""
    installed = {f.name for f in font_manager.fontManager.ttflist}
    for name in candidates:
        if name in installed:
            return name
    return candidates[-1]


SANS = _first_available(["Source Sans 3", "Segoe UI", "DejaVu Sans"])
SERIF = _first_available(["Source Serif 4", "Georgia", "DejaVu Serif"])
# Brand weight is SemiBold; the fallback fonts only ship regular and bold.
TITLE_WEIGHT = "semibold" if SERIF == "Source Serif 4" else "bold"


def apply_style() -> None:
    """Set matplotlib defaults for the brand: no top/right spines, no grid, grey text."""
    plt.rcParams.update(
        {
            "font.family": [SANS],
            "axes.edgecolor": MID,
            "axes.labelcolor": LABEL,
            "xtick.color": LABEL,
            "ytick.color": LABEL,
            "text.color": SLATE,
            "axes.titlecolor": INK,
            "axes.titlesize": 16,
            "axes.titleweight": "bold",
            "axes.titlelocation": "left",
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": False,
            "legend.frameon": False,
            "figure.facecolor": "white",
            "axes.facecolor": "white",
        }
    )


def highlight(labels, focus):
    """Mulberry for the one category that matters, light grey for the rest."""
    return [MULBERRY if label == focus else LIGHT for label in labels]


def takeaway_title(fig, lines, subtitle=None, x=0.025, y=0.92, size=19, gap=0.075):
    """Left-aligned serif title that states the finding, with key words in Mulberry.

    `lines` is a list of lines; each line is a list of (text, color) pieces, so the
    highlighted words can sit anywhere. Leave about 0.26 of the figure height free at the
    top (fig.subplots_adjust(top=0.74)) for two lines plus a subtitle.
    """
    renderer = fig.canvas.get_renderer()
    for i, pieces in enumerate(lines):
        cursor = x
        for text, color in pieces:
            t = fig.text(
                cursor,
                y - i * gap,
                text,
                fontsize=size,
                fontweight=TITLE_WEIGHT,
                family=SERIF,
                color=color,
                ha="left",
                va="baseline",
            )
            cursor += t.get_window_extent(renderer).width / fig.bbox.width
    if subtitle:
        fig.text(
            x,
            y - (len(lines) - 1) * gap - 0.065,
            subtitle,
            fontsize=12,
            color=SLATE,
            ha="left",
            va="baseline",
        )


def add_source(fig, text: str) -> None:
    """Add a grey source line at the bottom left of the figure."""
    fig.text(0.01, 0.01, text, fontsize=9, color=LABEL, ha="left", va="bottom")
