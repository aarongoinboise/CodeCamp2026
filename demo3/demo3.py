"""
scraper.py — Resilient box score scraper (function library)
=============================================================
Call parse_args() to get the source, then use:
  - load_html(args)        → raw HTML string
  - scrape_resilient(html) → structured dict
  - send_discord(data)     → sends stats to Discord

Args (exactly one per run):
  --v1     hosted HTML, V1 layout (table + semantic classes)
  --v2     hosted HTML, V2 layout (table + data-* attributes)
  --v3     hosted HTML, V3 layout (div/span grid, no table)
  --espn   fetch live from ESPN via requests
"""

from bs4 import BeautifulSoup
import re
import argparse
import os
import requests
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()

# ── URLs ──────────────────────────────────────────────────────────────────────

ESPN_URL = "https://www.espn.com/mens-college-basketball/boxscore/_/gameId/401856600"
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")
V1_URL   = "https://your-v1-url-here.com"
V2_URL   = "https://your-v2-url-here.com"
V3_URL   = "https://your-v3-url-here.com"

COL_ORDER = ["name", "min", "pts", "fg", "3pt", "ft", "reb", "ast", "to", "stl", "blk"]


# =============================================================================
# ARG PARSING
# =============================================================================

def parse_args():
    parser = argparse.ArgumentParser(description="Resilient ESPN box score scraper")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--v1",   action="store_true", help="Hosted HTML, V1 layout (table + semantic classes)")
    group.add_argument("--v2",   action="store_true", help="Hosted HTML, V2 layout (table + data-* attributes)")
    group.add_argument("--v3",   action="store_true", help="Hosted HTML, V3 layout (div/span grid, no table)")
    group.add_argument("--espn", action="store_true", help="Fetch live from ESPN via requests")
    return parser.parse_args()


# =============================================================================
# HTML LOADING
# =============================================================================

def load_html(args) -> str:
    if args.espn:
        url = ESPN_URL
    elif args.v1:
        url = V1_URL
    elif args.v2:
        url = V2_URL
    elif args.v3:
        url = V3_URL

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        )
    }
    resp = requests.get(url, headers=headers, timeout=15)
    resp.raise_for_status()
    return resp.text


# =============================================================================
# PARSING
# =============================================================================

def looks_like_stat_row(cells):
    attempts = sum(1 for c in cells if re.match(r"^\d{1,2}-\d{1,2}$", c.strip()))
    return attempts >= 2


def extract_score(soup):
    candidates = []
    for el in soup.find_all(string=re.compile(r"^\d{2,3}$")):
        text = el.strip()
        parent_tag = el.parent.name
        if parent_tag not in ("td", "th", "li", "script", "style"):
            try:
                val = int(text)
                if 40 <= val <= 200:
                    candidates.append((val, el))
            except ValueError:
                pass
    candidates.sort(key=lambda x: -x[0])
    if len(candidates) >= 2:
        return [str(candidates[0][0]), str(candidates[1][0])]
    return []


def extract_team_names(soup):
    names = []
    selectors = [
        ("span", re.compile(r"^team.?name$",           re.I)),
        ("span", re.compile(r"ScoreHeader__TeamName",  re.I)),
        ("span", re.compile(r"^long.?name$",           re.I)),
        ("div",  re.compile(r"ScoreCell__TeamName|teamName", re.I)),
        ("span", re.compile(r"ScoreCell__TeamName|teamName", re.I)),
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
    players = []
    totals  = []

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
        if cells[0].upper() in ("STARTERS", "BENCH", "MIN", "PLAYER"):
            continue

        row_classes = " ".join(row.get("class", []))
        is_starter  = "bench" not in row_classes.lower()

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
    soup = BeautifulSoup(html, "html.parser")
    players, totals = extract_players(soup)
    return {
        "scores":     extract_score(soup),
        "team_names": extract_team_names(soup),
        "players":    players,
        "totals":     totals,
    }


# =============================================================================
# ANALYSIS
# =============================================================================

def analyze(data: dict):
    players    = data["players"]
    team_names = data.get("team_names", [])
    mid        = len(players) // 2

    def get_team(idx):
        if len(team_names) == 2:
            return team_names[0] if idx < mid else team_names[1]
        if len(team_names) == 1:
            return team_names[0]
        return "Unknown"

    for i, p in enumerate(players):
        p["team"] = get_team(i)

    teams = {}
    for p in players:
        teams.setdefault(p["team"], []).append(p)

    team_stats = {}
    for team, roster in teams.items():
        total_tov = 0
        total_fg  = 0
        total_fga = 0
        for p in roster:
            try: total_tov += int(p.get("to", 0) or 0)
            except: pass
            fg_str = p.get("fg", "0-0") or "0-0"
            try:
                made, att = fg_str.split("-")
                total_fg  += int(made)
                total_fga += int(att)
            except: pass
        fg_pct = total_fg / total_fga if total_fga else 0
        team_stats[team] = {"tov": total_tov, "fg_pct": fg_pct}

    t1, t2 = list(team_stats.keys())
    if team_stats[t1]["tov"] == team_stats[t2]["tov"] and team_stats[t1]["fg_pct"] == team_stats[t2]["fg_pct"]:
        advantage_str = "Even — no clear advantage"
    else:
        advantage_team = min(
            team_stats,
            key=lambda t: (team_stats[t]["tov"], -team_stats[t]["fg_pct"])
        )
        adv = team_stats[advantage_team]
        advantage_str = f"{advantage_team} (TOV: {adv['tov']}, FG%: {adv['fg_pct']:.1%})"

    player_scores = []
    for p in players:
        name = p.get("name", "")
        if not name:
            continue
        try:
            tov    = int(p.get("to", 0) or 0)
            fg_str = p.get("fg", "0-0") or "0-0"
            made, att = fg_str.split("-")
            fg_pct = int(made) / int(att) if int(att) > 0 else 0
            score  = fg_pct - (tov * 0.05)
            player_scores.append({
                "player": name,
                "team":   p["team"],
                "tov":    tov,
                "fg_pct": fg_pct,
                "score":  score,
            })
        except:
            continue

    top_props = sorted(player_scores, key=lambda x: x["score"], reverse=True)[:3]
    return advantage_str, top_props, team_stats


# =============================================================================
# DISCORD
# =============================================================================

def send_discord(data: dict):
    now = datetime.now().strftime("%b %d %Y %I:%M %p")
    advantage_str, top_props, team_stats = analyze(data)

    scores     = data.get("scores", [])
    team_names = data.get("team_names", ["Team 1", "Team 2"])
    score_line = (
        f"{team_names[0]} {scores[0]} · {team_names[1]} {scores[1]}"
        if len(scores) >= 2 and len(team_names) >= 2
        else "Score unavailable"
    )

    body  = f"**NCAA Championship — {' vs '.join(team_names)}**\n"
    body += f"`{score_line}`\n"
    body += f"`{now}`\n"
    body += f"\n**ADVANTAGE:** {advantage_str}\n"
    body += "\n**TEAM TOTALS**\n"
    for team, stats in team_stats.items():
        body += f"{team}: TOV {stats['tov']}  FG% {stats['fg_pct']:.1%}\n"
    body += "\n**TOP PROPS**\n"
    for p in top_props:
        body += f"{p['player']} ({p['team']})  FG% {p['fg_pct']:.1%}  TOV {p['tov']}\n"

    requests.post(DISCORD_WEBHOOK, json={"content": body})
    print("  ✓  Discord message sent.")
    
def run_espn():
    class Args:
        v1 = v2 = v3 = None
        espn = True
    html = load_html(Args())
    data = scrape_resilient(html)
    send_discord(data)