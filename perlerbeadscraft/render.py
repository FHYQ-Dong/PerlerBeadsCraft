"""Render a Pattern into a colour preview and a printable code chart."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from .pattern import EMPTY, Pattern


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
    light, dash, bold = (210, 210, 210), (140, 140, 140), (90, 90, 90)
    for c in range(cols + 1):
        x = c * cell
        if c % 10 == 0:
            draw.line([(x, 0), (x, rows * cell)], fill=bold, width=2)
        elif c % 5 == 0:
            _dashed_line(draw, (x, 0), (x, rows * cell), dash)
        else:
            draw.line([(x, 0), (x, rows * cell)], fill=light, width=1)
    for r in range(rows + 1):
        y = r * cell
        if r % 10 == 0:
            draw.line([(0, y), (cols * cell, y)], fill=bold, width=2)
        elif r % 5 == 0:
            _dashed_line(draw, (0, y), (cols * cell, y), dash)
        else:
            draw.line([(0, y), (cols * cell, y)], fill=light, width=1)


def _dashed_line(draw, p0, p1, fill, *, width=1, dash=6, gap=4) -> None:
    """Draw a dashed axis-aligned line from p0 to p1."""
    x0, y0 = p0
    x1, y1 = p1
    if x0 == x1:  # vertical
        y = y0
        while y < y1:
            draw.line([(x0, y), (x0, min(y + dash, y1))], fill=fill, width=width)
            y += dash + gap
    else:  # horizontal
        x = x0
        while x < x1:
            draw.line([(x, y0), (min(x + dash, x1), y0)], fill=fill, width=width)
            x += dash + gap


def render_chart(
    pattern: Pattern,
    out_path: str | Path,
    *,
    show_codes: bool = True,
    dpi: int = 150,
) -> Path:
    """Render a printable chart: colour grid + the bead code in each cell + legend.

    Imports matplotlib lazily so the rest of the package stays light.
    """
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch

    grid_rgb = _rgb_grid(pattern)
    rows, cols = pattern.rows, pattern.cols

    fig_w = cols * 0.32 + 4.5  # extra room for the legend column
    fig_h = max(rows * 0.32, 3) + 0.5
    fig, ax = plt.subplots(figsize=(fig_w, fig_h), dpi=dpi)

    ax.imshow(grid_rgb, extent=(0, cols, rows, 0), interpolation="nearest")

    # Bead code in every cell (skip when too dense to be legible).
    if show_codes and rows * cols <= 6000:
        max_len = max((len(c.code) for _, c, _ in pattern.used_colors()), default=2)
        fontsize = 5.5 if max_len <= 2 else 4.5 if max_len == 3 else 3.7
        for r in range(rows):
            for c in range(cols):
                idx = int(pattern.grid[r, c])
                if idx == EMPTY:
                    continue
                color = pattern.palette.colors[idx]
                ax.text(
                    c + 0.5, r + 0.5, color.code,
                    ha="center", va="center", fontsize=fontsize,
                    color=np.array(_text_color(color.rgb)) / 255,
                )

    _matplotlib_grid(ax, rows, cols)

    handles = [
        Patch(
            facecolor=np.array(color.rgb) / 255,
            edgecolor="#444",
            label=f"{color.label}  {color.hex}  ×{count}",
        )
        for _idx, color, count in pattern.used_colors()
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


def render_color_maps(
    pattern: Pattern,
    out_dir: str | Path,
    *,
    show_codes: bool = True,
    dpi: int = 150,
) -> list[Path]:
    """One image per used colour: that colour's beads marked, everything else blank.

    Files are named ``<rank>_<code>_x<count>.png`` (rank by usage, most-used first)
    so they sort in a sensible placing order. Returns the written paths.
    """
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    rows, cols = pattern.rows, pattern.cols
    used = pattern.used_colors()
    paths: list[Path] = []

    for rank, (idx, color, count) in enumerate(used, start=1):
        mask = pattern.grid == idx
        grid_rgb = np.full((rows, cols, 3), 255, dtype=np.uint8)  # blank = white
        grid_rgb[mask] = color.rgb

        fig_w = max(cols * 0.30, 3) + 0.5
        fig_h = max(rows * 0.30, 3) + 0.8
        fig, ax = plt.subplots(figsize=(fig_w, fig_h), dpi=dpi)
        ax.imshow(grid_rgb, extent=(0, cols, rows, 0), interpolation="nearest")

        # Code in each marked cell so even pale colours are unmistakable.
        if show_codes and int(mask.sum()) <= 4000:
            fontsize = 5.5 if len(color.code) <= 2 else 4.5 if len(color.code) == 3 else 3.7
            text_color = np.array(_text_color(color.rgb)) / 255
            ys, xs = np.nonzero(mask)
            for y, x in zip(ys.tolist(), xs.tolist()):
                ax.text(
                    x + 0.5, y + 0.5, color.code,
                    ha="center", va="center", fontsize=fontsize, color=text_color,
                )

        _matplotlib_grid(ax, rows, cols)
        ax.set_title(
            f"{rank}/{len(used)}   {color.label}   {color.hex}   ×{count}",
            fontsize=10,
        )

        path = out_dir / f"{rank:02d}_{color.code}_x{count}.png"
        fig.savefig(path, bbox_inches="tight")
        plt.close(fig)
        paths.append(path)

    return paths


def _matplotlib_grid(ax, rows: int, cols: int) -> None:
    ax.set_xticks(np.arange(0, cols + 1, 10))
    ax.set_yticks(np.arange(0, rows + 1, 10))
    ax.set_xticks(np.arange(0, cols + 1, 1), minor=True)
    ax.set_yticks(np.arange(0, rows + 1, 1), minor=True)
    ax.grid(which="minor", color="#cccccc", linewidth=0.4)
    ax.grid(which="major", color="#555555", linewidth=1.1)
    # Dashed line every 5 cells (the halves between the bold every-10 lines).
    for x in range(5, cols, 10):
        ax.axvline(x, color="#888888", linewidth=0.7, linestyle=(0, (4, 3)), zorder=3)
    for y in range(5, rows, 10):
        ax.axhline(y, color="#888888", linewidth=0.7, linestyle=(0, (4, 3)), zorder=3)
    ax.tick_params(which="both", length=0, labelsize=7)
    ax.set_xlim(0, cols)
    ax.set_ylim(rows, 0)
    ax.set_aspect("equal")
