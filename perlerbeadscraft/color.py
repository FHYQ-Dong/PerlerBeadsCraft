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


def nearest_indices(pixels_rgb: np.ndarray, palette_rgb: np.ndarray) -> np.ndarray:
    """For each pixel (N, 3) return the index of the closest palette colour.

    Distance is squared Euclidean in Lab space.
    """
    pix_lab = srgb_to_lab(pixels_rgb)          # (N, 3)
    pal_lab = srgb_to_lab(palette_rgb)         # (M, 3)
    # (N, M) squared distances via |a-b|^2 = |a|^2 + |b|^2 - 2 a.b
    dists = (
        (pix_lab**2).sum(axis=1)[:, None]
        + (pal_lab**2).sum(axis=1)[None, :]
        - 2 * pix_lab @ pal_lab.T
    )
    return np.argmin(dists, axis=1)
