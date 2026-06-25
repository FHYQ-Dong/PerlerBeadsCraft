"""Turn an image into a grid of bead colours."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageEnhance

from .color import kmeans_lab, nearest_indices, nearest_lab, srgb_to_lab
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
    protect_accents: bool = False,
    min_color_distance: float = 0.0,
    saturation: float = 1.0,
    contrast: float = 1.0,
    alpha_threshold: int = 128,
    resample: Image.Resampling = Image.Resampling.LANCZOS,
) -> Pattern:
    """Load ``image_path`` and reduce it to a bead grid.

    ``width``/``height`` are measured in beads; give one to keep aspect ratio.
    Source pixels with alpha < ``alpha_threshold`` become empty cells.
    ``saturation``/``contrast`` pre-adjust the image (1.0 = unchanged) — useful
    for washed-out, high-key art.
    ``max_colors`` caps the number of distinct bead colours used.
    ``protect_accents`` keeps small but distinctly coloured regions from being
    merged away. ``min_color_distance`` (Lab deltaE) forbids picking two colours
    closer than that, so the budget isn't spent on near-duplicates.
    """
    img = Image.open(image_path).convert("RGBA")
    img = _adjust(img, saturation, contrast)
    cols, rows = _target_size(img.width, img.height, width, height)
    img = img.resize((cols, rows), resample)

    arr = np.asarray(img)                       # (rows, cols, 4)
    rgb = arr[..., :3].reshape(-1, 3)
    alpha = arr[..., 3].reshape(-1)
    mask = alpha >= alpha_threshold

    palette_rgb = np.array([c.rgb for c in palette.colors])
    if max_colors is not None:
        idx = _quantize_to_palette(
            rgb, mask, palette_rgb, max_colors, protect_accents, min_color_distance
        )
    else:
        idx = nearest_indices(rgb, palette_rgb)
    idx = idx.astype(int)
    idx[~mask] = EMPTY

    return Pattern(grid=idx.reshape(rows, cols), palette=palette)


def _adjust(img: Image.Image, saturation: float, contrast: float) -> Image.Image:
    """Apply saturation/contrast to the colour channels, leaving alpha intact."""
    if saturation == 1.0 and contrast == 1.0:
        return img
    r, g, b, a = img.split()
    rgb = Image.merge("RGB", (r, g, b))
    if saturation != 1.0:
        rgb = ImageEnhance.Color(rgb).enhance(saturation)
    if contrast != 1.0:
        rgb = ImageEnhance.Contrast(rgb).enhance(contrast)
    return Image.merge("RGBA", (*rgb.split(), a))


def _quantize_to_palette(
    rgb: np.ndarray,
    mask: np.ndarray,
    palette_rgb: np.ndarray,
    max_colors: int,
    protect_accents: bool = False,
    min_color_distance: float = 0.0,
) -> np.ndarray:
    """Pick a representative subset of ≤ ``max_colors`` bead colours, then map
    every cell to the nearest bead in that subset.

    The subset is chosen by clustering the cells' colours (k-means in Lab) and
    snapping each cluster centre to its nearest bead — so distinct accent colours
    survive instead of being out-voted by the most common hue. ``protect_accents``
    keeps small-but-distinct colours; ``min_color_distance`` forbids near-duplicate
    picks so the budget spreads over genuinely different colours.
    """
    out = np.zeros(len(rgb), dtype=int)
    cells = rgb[mask]
    if len(cells) == 0:
        return out

    cells_lab = srgb_to_lab(cells)
    palette_lab = srgb_to_lab(palette_rgb)

    # If the image already maps to few enough beads, no reduction is needed.
    full = nearest_lab(cells_lab, palette_lab)
    if len(np.unique(full)) <= max_colors:
        out[mask] = full
        return out

    if min_color_distance > 0:
        subset = _select_spaced(cells_lab, palette_lab, max_colors, min_color_distance)
    else:
        _labels, centers = kmeans_lab(cells_lab, max_colors)
        subset = list(dict.fromkeys(nearest_lab(centers, palette_lab).tolist()))

    if protect_accents:
        subset = _protect_accents(subset, full, cells_lab, palette_lab, max_colors)

    subset_arr = np.array(subset)
    out[mask] = subset_arr[nearest_lab(cells_lab, palette_lab[subset_arr])]
    return out


def _select_spaced(
    cells_lab: np.ndarray, palette_lab: np.ndarray, max_colors: int, min_dist: float
) -> list[int]:
    """Choose up to ``max_colors`` beads, all ≥ ``min_dist`` apart in Lab.

    Builds a rich candidate pool (a finer k-means than the budget), ranks beads
    by how much of the image they cover, then greedily keeps the biggest that
    isn't within ``min_dist`` of one already kept. Near-duplicates are skipped,
    so the budget goes to genuinely different colours.
    """
    pool_k = min(max_colors * 3, len(cells_lab))
    labels, centers = kmeans_lab(cells_lab, pool_k)
    areas = np.bincount(labels, minlength=len(centers))
    beads = nearest_lab(centers, palette_lab)

    bead_area: dict[int, int] = {}
    for bead, area in zip(beads.tolist(), areas.tolist()):
        bead_area[bead] = bead_area.get(bead, 0) + int(area)

    kept: list[int] = []
    kept_lab: list[np.ndarray] = []
    for bead in sorted(bead_area, key=bead_area.get, reverse=True):
        lab = palette_lab[bead]
        if all(np.sqrt(((lab - kl) ** 2).sum()) >= min_dist for kl in kept_lab):
            kept.append(bead)
            kept_lab.append(lab)
            if len(kept) == max_colors:
                break
    return kept


# Accent-protection thresholds (Lab deltaE / area fraction).
_ACCENT_DISTINCT = 20.0   # cells this far from the subset are under-represented
_ACCENT_REDUNDANT = 12.0  # two subset colours this close are near-duplicates


def _protect_accents(
    subset: list[int],
    full: np.ndarray,
    cells_lab: np.ndarray,
    palette_lab: np.ndarray,
    max_colors: int,
) -> list[int]:
    """Make small but distinctly-coloured regions survive the colour cap.

    Works from the cells the subset represents *badly*: it clusters those
    under-represented cells, and any cluster big enough and distinct enough is a
    dropped accent. Each is added to a free slot, or swapped in for the less-used
    half of the closest near-duplicate pair — so it never degrades a palette
    k-means already got right (no missing accent, or nothing redundant to spare).
    """
    subset = list(subset)
    total = len(cells_lab)
    min_area = max(3, round(0.002 * total))    # ignore anti-aliasing fringe / noise

    sub_lab = palette_lab[subset]
    assign = nearest_lab(cells_lab, sub_lab)
    error = np.sqrt(((cells_lab - sub_lab[assign]) ** 2).sum(axis=1))
    under = error >= _ACCENT_DISTINCT
    if int(under.sum()) < min_area:
        return subset                          # subset represents everything well

    # Cluster the under-represented cells; large clusters are the missing colours.
    labels, centers = kmeans_lab(cells_lab[under], max(1, max_colors // 2))
    candidates: list[tuple[int, int]] = []
    for j in range(len(centers)):
        area = int((labels == j).sum())
        if area < min_area:
            continue
        bead = int(nearest_lab(centers[j][None, :], palette_lab)[0])
        if bead in subset:
            continue
        candidates.append((area, bead))
    candidates.sort(reverse=True)              # largest accent first

    for _area, bead in candidates:
        if bead in subset:
            continue
        if len(subset) < max_colors:           # free slot — just add it
            subset.append(bead)
            continue
        # Otherwise sacrifice the less-used half of the closest near-duplicate pair.
        sub_lab = palette_lab[subset]
        pair = np.sqrt(((sub_lab[:, None, :] - sub_lab[None, :, :]) ** 2).sum(axis=2))
        np.fill_diagonal(pair, np.inf)
        if float(pair.min()) >= _ACCENT_REDUNDANT:
            break                              # nothing redundant to spare; respect the cap
        i, j = np.unravel_index(np.argmin(pair), pair.shape)
        assign = nearest_lab(cells_lab, sub_lab)
        drop = i if (assign == i).sum() <= (assign == j).sum() else j
        subset[drop] = bead
    return subset
