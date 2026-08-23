#!/usr/bin/env python3
"""gh-heat web add-on: GitHub contribution heatmap SVG generator.

Fetches GitHub's own contribution calendar (public, no auth) and renders
GitHub-exact SVGs (current light/dark palettes) for embedding or MCP use.

Usage:
    python3 tools/ghheat.py gen <user> [--dark] [--out PATH] [--width N]
    python3 tools/ghheat.py fetch <user>   # print {date: level} JSON

Stdlib only — runs anywhere Python 3.9+ exists (no pip install needed).
"""

import argparse
import json
import re
import sys
import urllib.request
from datetime import date, timedelta

CAL_URL = "https://github.com/users/{user}/contributions"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"

PALETTES = {
    "light": {
        "bg": "#ffffff", "empty": "#ebedf0",
        1: "#9be9a8", 2: "#40c463", 3: "#30a14e", 4: "#216e39",
        "text": "#586069", "grid": "#c9d1d9",
    },
    "dark": {
        "bg": "#0d1117", "empty": "#161b22",
        1: "#0e4429", 2: "#006d32", 3: "#26a641", 4: "#39d353",
        "text": "#8b949e", "grid": "#21262d",
    },
}

CELL, GAP = 10, 2
PITCH = CELL + GAP
LABEL_W = 30          # weekday label gutter
TOP = 20              # month label gutter
BOTTOM = 26           # legend gutter
WEEKS = 53


def fetch_calendar(username: str) -> dict:
    """Return (date -> level 0..4) plus total contributions count."""
    url = CAL_URL.format(user=username)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as resp:
        html = resp.read().decode("utf-8", "replace")

    levels = {}
    for m in re.finditer(r'data-date="(\d{4}-\d{2}-\d{2})"[^>]*?data-level="(\d)"', html):
        levels[m.group(1)] = int(m.group(2))

    total = None
    m = re.search(r'>([\d,]+)\s+contributions? in the last year', html)
    if m:
        total = int(m.group(1).replace(",", ""))
    if total is None and levels:
        total = sum(levels.values())
    return levels, total


def week_grid(levels: dict) -> list:
    """53 weeks x 7 rows (Sun..Sat) of levels, ending at the current week."""
    today = date.today()
    start = today - timedelta(days=WEEKS * 7)
    # first column starts on the Sunday on/before start
    start -= timedelta(days=(start.weekday() + 1) % 7)
    columns = []
    for w in range(WEEKS):
        col = []
        for r in range(7):
            d = start + timedelta(days=w * 7 + r)
            col.append(levels.get(d.isoformat(), 0))
        columns.append(col)
    return columns, start


def render_svg(username: str, dark: bool, cols: list, total: int) -> str:
    p = PALETTES["dark" if dark else "light"]
    w = LABEL_W + WEEKS * PITCH + 10
    h = TOP + 7 * PITCH + BOTTOM
    font = "font-family='-apple-system,BlinkMacSystemFont,Segoe UI,Helvetica,Arial,sans-serif'"

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-label="{username} contribution graph">',
        f'<rect width="{w}" height="{h}" fill="{p["bg"]}"/>',
    ]

    # month labels inserted in gen() (needs grid start date)

    # weekday labels (Mon/Wed/Fri like GitHub)
    for r, name in ((1, "Mon"), (3, "Wed"), (5, "Fri")):
        y = TOP + r * PITCH + CELL - 1
        parts.append(f'<text x="{LABEL_W - 6}" y="{y}" font-size="9" text-anchor="end" fill="{p["text"]}" {font}>{name}</text>')

    # cells
    for wi, col in enumerate(cols):
        x = LABEL_W + wi * PITCH
        for r, lvl in enumerate(col):
            y = TOP + r * PITCH
            fill = p["empty"] if lvl == 0 else p[lvl]
            parts.append(f'<rect x="{x}" y="{y}" width="{CELL}" height="{CELL}" rx="2" fill="{fill}"/>')

    # legend
    lx = LABEL_W
    ly = TOP + 7 * PITCH + 7
    parts.append(f'<text x="{lx}" y="{ly}" font-size="9" fill="{p["text"]}" {font}>Less</text>')
    for i, lvl in enumerate((0, 1, 2, 3, 4)):
        fill = p["empty"] if lvl == 0 else p[lvl]
        parts.append(f'<rect x="{lx + 30 + i * 12}" y="{ly - 8}" width="10" height="10" rx="2" fill="{fill}"/>')
    parts.append(f'<text x="{lx + 30 + 5 * 12 + 4}" y="{ly}" font-size="9" fill="{p["text"]}" {font}>More</text>')

    if total is not None:
        parts.append(f'<text x="{w - 10}" y="{ly}" font-size="9" text-anchor="end" fill="{p["text"]}" {font}>{total} contributions in the last year</text>')

    if dark:
        parts.append('<rect width="%d" height="%d" fill="none" stroke="%s" stroke-width="1"/>' % (w, h, p["grid"]))

    parts.append("</svg>")
    return "\n".join(parts)


def month_labels(cols, grid_start) -> list:
    labels, prev = [], None
    for wi in range(WEEKS):
        d = grid_start + timedelta(days=wi * 7)
        label = d.strftime("%b")
        if label != prev:
            labels.append((wi, label))
            prev = label
    return labels


def gen(username: str, dark: bool, width: int | None) -> str:
    levels, total = fetch_calendar(username)
    cols, grid_start = week_grid(levels)
    svg = render_svg(username, dark, cols, total)

    # insert month labels after the background rect (position: index of first > rect)
    labels = month_labels(cols, grid_start)
    text = "".join(
        f'<text x="{LABEL_W + wi * PITCH}" y="12" font-size="9" fill="{PALETTES["dark" if dark else "light"]["text"]}" '
        f"font-family='-apple-system,BlinkMacSystemFont,Segoe UI,Helvetica,Arial,sans-serif'>{label}</text>"
        for wi, label in labels
    )
    # place right after the background rect line
    svg = svg.replace("</svg>", text + "</svg>")  # order irrelevant: absolute coords
    if width:
        svg = re.sub(r'width="\d+"', f'width="{width}"', svg, count=1)
    return svg


def main() -> int:
    ap = argparse.ArgumentParser(description="GitHub contribution heatmap generator")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_gen = sub.add_parser("gen", help="render SVG")
    p_gen.add_argument("user")
    p_gen.add_argument("--dark", action="store_true")
    p_gen.add_argument("--out", default=None)
    p_gen.add_argument("--width", type=int, default=None)

    p_fetch = sub.add_parser("fetch", help="print {date: level} JSON")
    p_fetch.add_argument("user")

    args = ap.parse_args()

    if args.cmd == "fetch":
        levels, total = fetch_calendar(args.user)
        print(json.dumps({"levels": levels, "total": total}))
        return 0

    try:
        svg = gen(args.user, args.dark, args.width)
    except urllib.error.HTTPError as e:
        print(f"error: GitHub returned {e.code} for user {args.user!r}" +
              (" (no such user?)" if e.code == 404 else ""), file=sys.stderr)
        return 1
    if args.out:
        with open(args.out, "w") as fh:
            fh.write(svg)
        print(f"wrote {args.out} ({len(svg)} bytes)")
    else:
        print(svg)
    return 0


if __name__ == "__main__":
    sys.exit(main())
