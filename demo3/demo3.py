"""
scraper.py — Resilient box score scraper (function library)
=============================================================
Call parse_args() to get the source, then use:
  - load_html(args)        → raw HTML string
  - scrape_resilient(html) → structured dict
  - save_csv(data, path)   → writes CSV

Args (exactly one per run):
  --v1 FILE    local HTML, V1 layout (table + semantic classes)
  --v2 FILE    local HTML, V2 layout (table + data-* attributes)
  --v3 FILE    local HTML, V3 layout (div/span grid, no table)
  --espn       fetch live from ESPN via requests
"""

from bs4 import BeautifulSoup
import re
import csv
import argparse

# ── ESPN live URL ─────────────────────────────────────────────────────────────

ESPN_URL = "https://www.espn.com/mens-college-basketball/boxscore/_/gameId/401856600"

# Column order ESPN always uses — position-based, never rely on class names
COL_ORDER = ["name", "min", "pts", "fg", "3pt", "ft", "reb", "ast", "to", "stl", "blk"]

CSV_FIELDS = [
    "team", "player", "starter",
    "MIN", "PTS", "FG", "3PT", "FT",
    "REB", "AST", "TO", "STL", "BLK",
    "OREB", "DREB", "PF",
]


# =============================================================================
# ARG PARSING
# =============================================================================

def parse_args():
    """
    Parse CLI args. Enforces exactly one source flag per run.
    Returns argparse.Namespace with attrs: v1, v2, v3, espn
    """
    parser = argparse.ArgumentParser(description="Resilient ESPN box score scraper")

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--v1",   metavar="FILE", help="Local HTML, V1 layout (table + semantic classes)")
    group.add_argument("--v2",   metavar="FILE", help="Local HTML, V2 layout (table + data-* attributes)")
    group.add_argument("--v3",   metavar="FILE", help="Local HTML, V3 layout (div/span grid, no table)")
    group.add_argument("--espn", action="store_true", help="Fetch live from ESPN via requests")

    return parser.parse_args()


# =============================================================================
# HTML LOADING
# =============================================================================

def load_html(args) -> str:
    """
    Load raw HTML from the source indicated by parsed args.
    --v1/v2/v3: reads the given local file path.
    --espn:     fetches the live ESPN page with a browser User-Agent.
    Returns the raw HTML string.
    """
    if args.espn:
        import requests
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            )
        }
        resp = requests.get(ESPN_URL, headers=headers, timeout=15)
        resp.raise_for_status()
        return resp.text

    # --v1, --v2, --v3 all point to a local file path
    path = args.v1 or args.v2 or args.v3
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


# =============================================================================
# PARSING — resilient, position-based, layout-agnostic
# =============================================================================

def looks_like_stat_row(cells):
    """True if the row has at least 2 shot-attempt patterns like '5-11'."""
    attempts = sum(1 for c in cells if re.match(r"^\d{1,2}-\d{1,2}$", c.strip()))
    return attempts >= 2


def extract_score(soup):
    """
    Find the final score by locating prominent numeric text nodes
    outside of table cells (scores live in headers, not stat rows).
    Returns [score1, score2] as strings, highest first.
    """
    candidates = []
    for el in soup.find_all(string=re.compile(r"^\d{2,3}$")):
        text = el.strip()
        parent_tag = el.parent.name
        if parent_tag not in ("td", "th", "li", "script", "style"):
            try:
                val = int(text)
                if 40 <= val <= 200:  # realistic finished-game score range
                    candidates.append((val, el))
            except ValueError:
                pass
    candidates.sort(key=lambda x: -x[0])
    if len(candidates) >= 2:
        return [str(candidates[0][0]), str(candidates[1][0])]
    return []


def extract_team_names(soup):
    """
    Pull team names across all 3 local HTML layouts and live ESPN.
    Tries progressively broader selectors; returns up to 2 names.
    """
    names = []
    selectors = [
        ("span", re.compile(r"^team.?name$",           re.I)),  # V1
        ("span", re.compile(r"ScoreHeader__TeamName",  re.I)),  # V2
        ("span", re.compile(r"^long.?name$",           re.I)),  # V3
        ("div",  re.compile(r"ScoreCell__TeamName|teamName", re.I)),  # live ESPN
        ("span", re.compile(r"ScoreCell__TeamName|teamName", re.I)),  # live ESPN alt
    ]
    for tag, cls in selectors:
        for el in soup.find_all(tag, class_=cls):
            t = el.get_text(strip=True)
            if t and len(t) > 3 and not t.isdigit() and t not in names:
                names.append(t)
        if len(names) >= 2:
            break
    return names[:2]


def extract_players(soup):
    """
    Extract player rows regardless of table vs div/span layout.
    Uses column position for stat identity — ESPN column order is always:
      name, min, pts, fg, 3pt, ft, reb, ast, to, stl, blk

    Returns:
      players: list of dicts for individual players
      totals:  list of dicts for TEAM total rows
    """
    players = []
    totals  = []

    # Candidates from both table-based and div-based layouts
    row_candidates = soup.find_all("tr") + soup.find_all(
        "div", class_=re.compile(r"(row|athlete)", re.I)
    )

    for row in row_candidates:
        cells = [
            el.get_text(strip=True)
            for el in row.find_all(["td", "th", "span"])
            if el.get_text(strip=True)
        ]

        if len(cells) < 5:
            continue
        if not looks_like_stat_row(cells):
            continue
        # Skip header rows
        if cells[0].upper() in ("STARTERS", "BENCH", "MIN", "PLAYER"):
            continue

        row_classes = " ".join(row.get("class", []))
        is_starter  = "bench" not in row_classes.lower()

        # Team totals row
        if cells[0].upper() in ("TEAM", "TOTALS"):
            row_data = {col: (cells[i] if i < len(cells) else None)
                        for i, col in enumerate(COL_ORDER)}
            row_data["starter"] = None
            totals.append(row_data)
            continue

        row_data = {col: (cells[i] if i < len(cells) else None)
                    for i, col in enumerate(COL_ORDER)}
        row_data["starter"] = "Y" if is_starter else "N"
        players.append(row_data)

    return players, totals


def scrape_resilient(html: str) -> dict:
    """
    Main scrape entry point. Parses raw HTML and returns:
      {
        "scores":     [score1, score2],
        "team_names": [team1, team2],
        "players":    [...],
        "totals":     [...],
      }
    """
    soup = BeautifulSoup(html, "html.parser")
    players, totals = extract_players(soup)
    return {
        "scores":     extract_score(soup),
        "team_names": extract_team_names(soup),
        "players":    players,
        "totals":     totals,
    }


# =============================================================================
# CSV OUTPUT
# =============================================================================

def save_csv(data: dict, out_path: str):
    """
    Write player rows to CSV with columns:
      team, player, starter, MIN, PTS, FG, 3PT, FT,
      REB, AST, TO, STL, BLK, OREB, DREB, PF

    Team assignment: the player list is split in half — first half gets
    team_names[0], second half gets team_names[1]. ESPN always lists one
    full team then the other.

    OREB, DREB, PF are left blank when not present in the source HTML.
    """
    players    = data["players"]
    team_names = data.get("team_names", [])

    mid = len(players) // 2

    def get_team(idx):
        if len(team_names) == 2:
            return team_names[0] if idx < mid else team_names[1]
        if len(team_names) == 1:
            return team_names[0]
        return ""

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for i, p in enumerate(players):
            writer.writerow({
                "team":    get_team(i),
                "player":  p.get("name", ""),
                "starter": p.get("starter", ""),
                "MIN":     p.get("min", ""),
                "PTS":     p.get("pts", ""),
                "FG":      p.get("fg", ""),
                "3PT":     p.get("3pt", ""),
                "FT":      p.get("ft", ""),
                "REB":     p.get("reb", ""),
                "AST":     p.get("ast", ""),
                "TO":      p.get("to", ""),
                "STL":     p.get("stl", ""),
                "BLK":     p.get("blk", ""),
                "OREB":    "",  # not in simulated HTML
                "DREB":    "",  # not in simulated HTML
                "PF":      "",  # not in simulated HTML
            })