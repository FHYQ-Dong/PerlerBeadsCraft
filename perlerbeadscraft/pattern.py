"""Turn an image into a grid of bead colours."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image

from .color import nearest_indices, srgb_to_lab
from .palettes import BeadColor, Palette

EMPTY = -1  # marks a cell with no bead (transparent source pixel)


@dataclass
class Pattern:
    """A finished bead pattern.

    ``grid`` is a (rows, cols) int array of indices into ``palette.colors``,
    or ``EMPTY`` (-1) for a hole. ``counts`` maps palette index -> bead count.
    """

    grid: np.ndarray
    palette: Palette

    @property
    def rows(self) -> int:
        return self.grid.shape[0]

    @property
    def cols(self) -> int:
        return self.grid.shape[1]

    @property
    def counts(self) -> dict[int, int]:
        vals, freqs = np.unique(self.grid[self.grid != EMPTY], return_counts=True)
        return {int(v): int(c) for v, c in zip(vals, freqs)}

    @property
    def total_beads(self) -> int:
        return int((self.grid != EMPTY).sum())

    def used_colors(self) -> list[tuple[int, BeadColor, int]]:
        """(index, BeadColor, count) for each colour used, most-used first."""
        counts = self.counts
        order = sorted(counts, key=lambda i: counts[i], reverse=True)
        return [(i, self.palette.colors[i], counts[i]) for i in order]


def _target_size(src_w: int, src_h: int, width: int | None, height: int | None) -> tuple[int, int]:
    if width and height:
        return width, height
    if width:
        return width, max(1, round(src_h * width / src_w))
    if height:
        return max(1, round(src_w * height / src_h)), height
    raise ValueError("Provide at least one of width or height.")


def generate_pattern(
    image_path: str | Path,
    palette: Palette,
    width: int | None = None,
    height: int | None = None,
    *,
    max_colors: int | None = None,
    alpha_threshold: int = 128,
    resample: Image.Resampling = Image.Resampling.LANCZOS,
) -> Pattern:
    """Load ``image_path`` and reduce it to a bead grid.

    ``width``/``height`` are measured in beads; give one to keep aspect ratio.
    Source pixels with alpha < ``alpha_threshold`` become empty cells.
    ``max_colors`` caps the number of distinct bead colours used.
    """
    img = Image.open(image_path).convert("RGBA")
    cols, rows = _target_size(img.width, img.height, width, height)
    img = img.resize((cols, rows), resample)

    arr = np.asarray(img)                       # (rows, cols, 4)
    rgb = arr[..., :3].reshape(-1, 3)
    alpha = arr[..., 3].reshape(-1)

    palette_rgb = np.array([c.rgb for c in palette.colors])
    idx = nearest_indices(rgb, palette_rgb)
    idx[alpha < alpha_threshold] = EMPTY

    grid = idx.reshape(rows, cols)
    if max_colors is not None:
        grid = _reduce_colors(grid, palette_rgb, max_colors)

    return Pattern(grid=grid, palette=palette)


def _reduce_colors(grid: np.ndarray, palette_rgb: np.ndarray, max_colors: int) -> np.ndarray:
    """Keep the ``max_colors`` most-used bead colours; remap the rest to the
    nearest kept colour (in Lab space)."""
    mask = grid != EMPTY
    used = grid[mask]
    if used.size == 0:
        return grid

    vals, freqs = np.unique(used, return_counts=True)
    if len(vals) <= max_colors:
        return grid

    keep = vals[np.argsort(freqs)[::-1][:max_colors]]
    drop = np.setdiff1d(vals, keep)

    keep_lab = srgb_to_lab(palette_rgb[keep])
    new = grid.copy()
    for d in drop:
        d_lab = srgb_to_lab(palette_rgb[d][None, :])[0]
        nearest = keep[np.argmin(((keep_lab - d_lab) ** 2).sum(axis=1))]
        new[grid == d] = nearest
    return new
