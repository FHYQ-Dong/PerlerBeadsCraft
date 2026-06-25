"""Bead colour palettes.

The Hama Midi palette below (53 standard solid colours, code + hex) is taken
from the public Hama colour chart compiled at pixel-beads.com. Codes are the
official Hama numbers (e.g. ``H18`` is black). Where a colour has a widely
recognised name it is filled in; otherwise the code doubles as the name.
"""

from __future__ import annotations

from dataclasses import dataclass

from ._mard_data import MARD_MIDI_RAW


@dataclass(frozen=True)
class BeadColor:
    code: str
    rgb: tuple[int, int, int]
    name: str = ""

    @property
    def label(self) -> str:
        """Human label for legends: ``code`` or ``code · name``."""
        return f"{self.code} · {self.name}" if self.name else self.code

    @property
    def hex(self) -> str:
        return "#{:02X}{:02X}{:02X}".format(*self.rgb)


@dataclass(frozen=True)
class Palette:
    name: str
    colors: tuple[BeadColor, ...]

    def __len__(self) -> int:
        return len(self.colors)


def _hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


# (code, hex) for the 53 Hama Midi standard solids.
_HAMA_MIDI_RAW: tuple[tuple[str, str], ...] = (
    ("H01", "#ECEDED"), ("H02", "#F0E8B9"), ("H03", "#F0B901"), ("H04", "#E64F27"),
    ("H05", "#B63136"), ("H06", "#E1889F"), ("H07", "#694A82"), ("H08", "#2C4690"),
    ("H09", "#305CB0"), ("H10", "#256847"), ("H11", "#49AE89"), ("H12", "#534137"),
    ("H17", "#83888A"), ("H18", "#2E2F31"), ("H20", "#7F332A"), ("H21", "#A5693F"),
    ("H22", "#A52D36"), ("H26", "#DE9B90"), ("H27", "#DEB48B"), ("H28", "#363F38"),
    ("H29", "#B9395E"), ("H30", "#592F38"), ("H31", "#6797AE"), ("H33", "#FF3956"),
    ("H43", "#F0EA37"), ("H44", "#EE6972"), ("H45", "#886DB9"), ("H46", "#629ED7"),
    ("H47", "#83CB70"), ("H48", "#CF70B7"), ("H49", "#4998BC"), ("H60", "#F49422"),
    ("H70", "#B6B6D4"), ("H71", "#464541"), ("H75", "#BF7B4D"), ("H76", "#663317"),
    ("H77", "#EDE7DF"), ("H78", "#FFC99A"), ("H79", "#F08643"), ("H82", "#962F5C"),
    ("H83", "#0178A4"), ("H84", "#8B924C"), ("H95", "#F8CCE0"), ("H96", "#D4B1E3"),
    ("H97", "#A2D3FE"), ("H98", "#9ADBB1"), ("H101", "#A9C39B"), ("H102", "#356B2D"),
    ("H103", "#FFE660"), ("H104", "#BCD122"), ("H105", "#FFAC78"), ("H106", "#CCC5ED"),
    ("H107", "#6A87C1"),
)

# Conservative, widely-agreed names for the classic basics. Others stay code-only.
_HAMA_NAMES = {
    "H01": "White", "H02": "Cream", "H03": "Yellow", "H04": "Orange",
    "H05": "Red", "H06": "Pink", "H07": "Purple", "H08": "Dark Blue",
    "H09": "Blue", "H10": "Green", "H11": "Light Green", "H12": "Brown",
    "H17": "Grey", "H18": "Black", "H27": "Beige", "H60": "Bright Orange",
    "H76": "Dark Brown",
}

HAMA_MIDI = Palette(
    name="hama",
    colors=tuple(
        BeadColor(code=code, rgb=_hex_to_rgb(h), name=_HAMA_NAMES.get(code, ""))
        for code, h in _HAMA_MIDI_RAW
    ),
)

MARD_MIDI = Palette(
    name="mard",
    colors=tuple(
        BeadColor(code=code, rgb=_hex_to_rgb(h)) for code, h in MARD_MIDI_RAW
    ),
)

_PALETTES = {p.name: p for p in (MARD_MIDI, HAMA_MIDI)}
DEFAULT_PALETTE = "mard"


def list_palettes() -> list[str]:
    return sorted(_PALETTES)


def get_palette(name: str) -> Palette:
    try:
        return _PALETTES[name]
    except KeyError:
        raise ValueError(
            f"Unknown palette {name!r}. Available: {', '.join(list_palettes())}"
        ) from None
