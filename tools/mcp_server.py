#!/usr/bin/env python3
"""gh-heat MCP server: contribution heatmap as an agent-callable tool.

Exposes GitHub contribution heatmaps (authentic GitHub palettes, light/dark)
to MCP clients.

Run:  python3 tools/mcp_server.py
"""

import base64
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from mcp.server.fastmcp import FastMCP

from ghheat import fetch_calendar, render_svg, week_grid

mcp = FastMCP("gh-heat", instructions=(
    "Render GitHub contribution heatmaps as SVG. Use when a user wants their "
    "(or any public user's) contribution graph as an image, compares activity "
    "across users, or needs contribution totals."
))


@mcp.tool()
def generate_contribution_heatmap(
    username: str,
    dark_mode: bool = False,
) -> dict:
    """Render a GitHub contribution heatmap (last 12 months) as SVG.

    Args:
        username: GitHub username (public profiles, no auth).
        dark_mode: use GitHub's dark palette (squares #0e4429..#39d353 on #0d1117).

    Returns:
        dict: svg (string), contributions_last_year (int), weeks (int),
        data_url (base64 data URI for direct embedding).
    """
    levels, total = fetch_calendar(username)
    cols, _ = week_grid(levels)
    svg = render_svg(username, dark_mode, cols, total)

    return {
        "username": username,
        "svg": svg,
        "contributions_last_year": total,
        "weeks": len(cols),
        "data_url": "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode(),
    }


@mcp.tool()
def compare_contribution_activity(usernames: list[str]) -> dict:
    """Compare last-12-months contribution totals across public GitHub users.

    Args:
        usernames: list of GitHub usernames (1-10).
    """
    out = []
    for u in usernames[:10]:
        _, total = fetch_calendar(u)
        out.append({"username": u, "contributions_last_year": total})
    out.sort(key=lambda r: r["contributions_last_year"], reverse=True)
    return {"ranking": out}


if __name__ == "__main__":
    mcp.run()
