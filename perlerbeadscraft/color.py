"""Colour-space helpers: sRGB -> CIE L*a*b* and nearest-bead matching.

Matching is done in Lab space (CIE76 / Euclidean deltaE) because Euclidean
distance there tracks perceived colour difference far better than raw RGB.
"""

from __future__ import annotations

import numpy as np

# sRGB (D65) -> XYZ matrix and the D65 reference white.
_RGB_TO_XYZ = np.array(
    [
        [0.4124564, 0.3575761, 0.1804375],
        [0.2126729, 0.7151522, 0.0721750],
        [0.0193339, 0.1191920, 0.9503041],
    ]
)
_WHITE_D65 = np.array([0.95047, 1.00000, 1.08883])


def srgb_to_lab(rgb: np.ndarray) -> np.ndarray:
    """Convert an array of sRGB values (..., 3) in 0-255 to CIE Lab (..., 3)."""
    rgb = np.asarray(rgb, dtype=np.float64) / 255.0

    # sRGB gamma -> linear light.
    linear = np.where(rgb <= 0.04045, rgb / 12.92, ((rgb + 0.055) / 1.055) ** 2.4)

    xyz = linear @ _RGB_TO_XYZ.T
    xyz = xyz / _WHITE_D65

    eps = 216 / 24389
    kappa = 24389 / 27
    f = np.where(xyz > eps, np.cbrt(xyz), (kappa * xyz + 16) / 116)

    fx, fy, fz = f[..., 0], f[..., 1], f[..., 2]
    lab = np.empty_like(f)
    lab[..., 0] = 116 * fy - 16
    lab[..., 1] = 500 * (fx - fy)
    lab[..., 2] = 200 * (fy - fz)
    return lab


def nearest_lab(points_lab: np.ndarray, ref_lab: np.ndarray) -> np.ndarray:
    """For each point (N, 3) in Lab, the index of the nearest reference (M, 3)."""
    # (N, M) squared distances via |a-b|^2 = |a|^2 + |b|^2 - 2 a.b
    dists = (
        (points_lab**2).sum(axis=1)[:, None]
        + (ref_lab**2).sum(axis=1)[None, :]
        - 2 * points_lab @ ref_lab.T
    )
    return np.argmin(dists, axis=1)


def nearest_indices(pixels_rgb: np.ndarray, palette_rgb: np.ndarray) -> np.ndarray:
    """For each pixel (N, 3) return the index of the closest palette colour.

    Distance is squared Euclidean in Lab space.
    """
    return nearest_lab(srgb_to_lab(pixels_rgb), srgb_to_lab(palette_rgb))


def kmeans_lab(points: np.ndarray, k: int, *, seed: int = 0, iters: int = 30):
    """k-means in Lab space with k-means++ init. Returns (labels, centers).

    Deterministic for a given ``seed`` so the same image yields the same palette.
    """
    points = np.asarray(points, dtype=np.float64)
    n = len(points)
    k = min(k, n)
    rng = np.random.default_rng(seed)

    # k-means++ initialisation.
    centers = np.empty((k, points.shape[1]))
    centers[0] = points[rng.integers(n)]
    d2 = ((points - centers[0]) ** 2).sum(axis=1)
    for i in range(1, k):
        total = d2.sum()
        probs = d2 / total if total > 0 else np.full(n, 1 / n)
        centers[i] = points[rng.choice(n, p=probs)]
        d2 = np.minimum(d2, ((points - centers[i]) ** 2).sum(axis=1))

    labels = np.full(n, -1)
    for _ in range(iters):
        new_labels = nearest_lab(points, centers)
        if np.array_equal(new_labels, labels):
            break
        labels = new_labels
        for j in range(k):
            members = points[labels == j]
            if len(members):
                centers[j] = members.mean(axis=0)
            else:  # reseed an empty cluster on a random point
                centers[j] = points[rng.integers(n)]
    return labels, centers
