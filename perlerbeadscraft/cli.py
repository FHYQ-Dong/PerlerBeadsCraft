"""Command-line interface: image in, bead pattern out."""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

from .palettes import get_palette, list_palettes
from .pattern import generate_pattern
from .render import assign_symbols, render_chart, render_preview


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="perler",
        description="Turn an image into a Perler/Hama bead pattern (preview, chart, counts).",
    )
    p.add_argument("image", type=Path, help="Source image (png/jpg/...).")
    p.add_argument("-o", "--out-dir", type=Path, default=Path("output"),
                   help="Where to write outputs (default: ./output).")
    p.add_argument("-w", "--width", type=int, default=None,
                   help="Pattern width in beads (default 48 if no size given).")
    p.add_argument("--height", type=int, default=None,
                   help="Pattern height in beads. Give one of width/height to keep aspect ratio.")
    p.add_argument("-m", "--max-colors", type=int, default=None,
                   help="Cap the number of distinct bead colours used.")
    p.add_argument("-p", "--palette", default="hama", choices=list_palettes(),
                   help="Bead palette (default: hama).")
    p.add_argument("--bead-size", type=int, default=24,
                   help="Pixels per bead in the preview image (default 24).")
    p.add_argument("--shape", choices=("circle", "square"), default="circle",
                   help="Bead shape in the preview (default circle).")
    p.add_argument("--alpha-threshold", type=int, default=128,
                   help="Source pixels with alpha below this become empty cells (default 128).")
    p.add_argument("--no-symbols", action="store_true",
                   help="Omit per-cell symbols on the chart.")
    p.add_argument("--no-grid", action="store_true",
                   help="Omit grid lines on the colour preview.")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    if not args.image.exists():
        print(f"error: image not found: {args.image}", file=sys.stderr)
        return 1
    if args.width is None and args.height is None:
        args.width = 48

    palette = get_palette(args.palette)
    pattern = generate_pattern(
        args.image, palette,
        width=args.width, height=args.height,
        max_colors=args.max_colors,
        alpha_threshold=args.alpha_threshold,
    )

    args.out_dir.mkdir(parents=True, exist_ok=True)
    stem = args.image.stem
    preview_path = args.out_dir / f"{stem}_preview.png"
    chart_path = args.out_dir / f"{stem}_chart.png"
    csv_path = args.out_dir / f"{stem}_beads.csv"

    render_preview(pattern, preview_path, bead_px=args.bead_size,
                   shape=args.shape, draw_grid=not args.no_grid)
    render_chart(pattern, chart_path, show_symbols=not args.no_symbols)
    _write_counts_csv(pattern, csv_path)

    _print_summary(pattern, preview_path, chart_path, csv_path)
    return 0


def _write_counts_csv(pattern, path: Path) -> None:
    symbols = assign_symbols(pattern)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["symbol", "code", "name", "hex", "count"])
        for idx, color, count in pattern.used_colors():
            w.writerow([symbols[idx], color.code, color.name, color.hex, count])
        w.writerow([])
        w.writerow(["", "", "", "TOTAL", pattern.total_beads])


def _print_summary(pattern, preview_path, chart_path, csv_path) -> None:
    used = pattern.used_colors()
    print(f"Pattern: {pattern.cols} x {pattern.rows} beads "
          f"({pattern.total_beads} beads, {len(used)} colours)\n")
    symbols = assign_symbols(pattern)
    for idx, color, count in used:
        print(f"  {symbols[idx]:>2}  {color.label:<18} {color.hex}  x{count}")
    print("\nWrote:")
    for path in (preview_path, chart_path, csv_path):
        print(f"  {path}")


if __name__ == "__main__":
    raise SystemExit(main())
