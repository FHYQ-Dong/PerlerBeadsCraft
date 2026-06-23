"""Render a Pattern into a colour preview and a printable symbol chart."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from .pattern import EMPTY, Pattern

# Glyphs assigned to colours, in this order, for the printable chart.
_SYMBOLS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789abcdefghijklmnopqrstuvwxyz"
_SYMBOLS += "@#$%&*+=<>?/\\"


def assign_symbols(pattern: Pattern) -> dict[int, str]:
    """Map each used palette index to a unique glyph (most-used colour -> 'A')."""
    symbols: dict[int, str] = {}
    for n, (idx, _color, _count) in enumerate(pattern.used_colors()):
        symbols[idx] = _SYMBOLS[n] if n < len(_SYMBOLS) else "?"
    return symbols


def _rgb_grid(pattern: Pattern, empty=(255, 255, 255)) -> np.ndarray:
    """(rows, cols, 3) uint8 image; empty cells filled with ``empty``."""
    out = np.full((pattern.rows, pattern.cols, 3), empty, dtype=np.uint8)
    for idx, color, _ in pattern.used_colors():
        out[pattern.grid == idx] = color.rgb
    return out


def _text_color(rgb: tuple[int, int, int]) -> tuple[int, int, int]:
    """Black or white, whichever reads better on ``rgb``."""
    r, g, b = rgb
    luminance = 0.299 * r + 0.587 * g + 0.114 * b
    return (0, 0, 0) if luminance > 140 else (255, 255, 255)


def render_preview(
    pattern: Pattern,
    out_path: str | Path,
    *,
    bead_px: int = 24,
    shape: str = "circle",
    draw_grid: bool = True,
    background: tuple[int, int, int] = (255, 255, 255),
) -> Path:
    """Draw the finished craft as coloured beads on a grid. Returns the path."""
    w, h = pattern.cols * bead_px, pattern.rows * bead_px
    img = Image.new("RGB", (w, h), background)
    draw = ImageDraw.Draw(img)
    pad = max(1, bead_px // 12)
    hole = max(1, bead_px // 6)

    for r in range(pattern.rows):
        for c in range(pattern.cols):
            idx = int(pattern.grid[r, c])
            if idx == EMPTY:
                continue
            color = pattern.palette.colors[idx].rgb
            x0, y0 = c * bead_px + pad, r * bead_px + pad
            x1, y1 = (c + 1) * bead_px - pad, (r + 1) * bead_px - pad
            if shape == "square":
                draw.rectangle([x0, y0, x1, y1], fill=color)
            else:
                draw.ellipse([x0, y0, x1, y1], fill=color)
                # bead hole
                cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
                draw.ellipse(
                    [cx - hole, cy - hole, cx + hole, cy + hole], fill=background
                )

    if draw_grid:
        _draw_grid_lines(draw, pattern.rows, pattern.cols, bead_px)

    out_path = Path(out_path)
    img.save(out_path)
    return out_path


def _draw_grid_lines(draw: ImageDraw.ImageDraw, rows: int, cols: int, cell: int) -> None:
    light, bold = (210, 210, 210), (90, 90, 90)
    for c in range(cols + 1):
        x = c * cell
        wide = c % 10 == 0
        draw.line([(x, 0), (x, rows * cell)], fill=bold if wide else light, width=2 if wide else 1)
    for r in range(rows + 1):
        y = r * cell
        wide = r % 10 == 0
        draw.line([(0, y), (cols * cell, y)], fill=bold if wide else light, width=2 if wide else 1)


def render_chart(
    pattern: Pattern,
    out_path: str | Path,
    *,
    show_symbols: bool = True,
    dpi: int = 150,
) -> Path:
    """Render a printable chart: colour grid + per-cell symbols + legend.

    Imports matplotlib lazily so the rest of the package stays light.
    """
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch

    symbols = assign_symbols(pattern)
    grid_rgb = _rgb_grid(pattern)
    rows, cols = pattern.rows, pattern.cols

    fig_w = cols * 0.28 + 4.5  # extra room for the legend column
    fig_h = max(rows * 0.28, 3) + 0.5
    fig, ax = plt.subplots(figsize=(fig_w, fig_h), dpi=dpi)

    ax.imshow(grid_rgb, extent=(0, cols, rows, 0), interpolation="nearest")

    # Per-cell symbols (skip when too dense to be legible).
    if show_symbols and rows * cols <= 6000:
        for r in range(rows):
            for c in range(cols):
                idx = int(pattern.grid[r, c])
                if idx == EMPTY:
                    continue
                ax.text(
                    c + 0.5, r + 0.5, symbols[idx],
                    ha="center", va="center", fontsize=6,
                    color=np.array(_text_color(pattern.palette.colors[idx].rgb)) / 255,
                )

    _matplotlib_grid(ax, rows, cols)

    handles = [
        Patch(
            facecolor=np.array(color.rgb) / 255,
            edgecolor="#444",
            label=f"{symbols[idx]}  {color.label}  {color.hex}  ×{count}",
        )
        for idx, color, count in pattern.used_colors()
    ]
    ax.legend(
        handles=handles,
        loc="upper left",
        bbox_to_anchor=(1.02, 1.0),
        fontsize=8,
        title=f"{len(handles)} colours · {pattern.total_beads} beads · {cols}×{rows}",
        title_fontsize=9,
        handlelength=1.4,
        borderaxespad=0,
    )

    out_path = Path(out_path)
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)
    return out_path


def _matplotlib_grid(ax, rows: int, cols: int) -> None:
    ax.set_xticks(np.arange(0, cols + 1, 10))
    ax.set_yticks(np.arange(0, rows + 1, 10))
    ax.set_xticks(np.arange(0, cols + 1, 1), minor=True)
    ax.set_yticks(np.arange(0, rows + 1, 1), minor=True)
    ax.grid(which="minor", color="#cccccc", linewidth=0.4)
    ax.grid(which="major", color="#555555", linewidth=1.1)
    ax.tick_params(which="both", length=0, labelsize=7)
    ax.set_xlim(0, cols)
    ax.set_ylim(rows, 0)
    ax.set_aspect("equal")
