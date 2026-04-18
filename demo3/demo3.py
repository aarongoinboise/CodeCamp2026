from bs4 import BeautifulSoup
import pandas as pd
import re
import argparse
import os
import requests
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()

ESPN_URL = "https://www.espn.com/mens-college-basketball/boxscore/_/gameId/401856600"
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")
V1_URL = "https://aarongoinboise.github.io/CodeCamp2026/demo3/v1.html"
V2_URL = "https://aarongoinboise.github.io/CodeCamp2026/demo3/v2.html"
V3_URL = "https://aarongoinboise.github.io/CodeCamp2026/demo3/v3.html"


def parse_args():
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--v1",   action="store_true")
    group.add_argument("--v2",   action="store_true")
    group.add_argument("--v3",   action="store_true")
    group.add_argument("--espn", action="store_true")
    return parser.parse_args()


def load_html(args) -> str:
    url = ESPN_URL if args.espn else V1_URL if args.v1 else V2_URL if args.v2 else V3_URL
    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"}
    resp = requests.get(url, headers=headers, timeout=15)
    resp.raise_for_status()
    return resp.text


def is_stat_table(df):
    """Return True if this dataframe looks like a box score stat table."""
    cols = [str(c).upper() for c in df.columns]
    return any(c in cols for c in ["FG", "PTS", "MIN", "REB", "AST", "TO"])


def extract_players_from_tables(html):
    """Use pandas to grab all tables, find the stat ones, return player rows."""
    try:
        all_tables = pd.read_html(html)
    except Exception:
        return [], []

    stat_tables = [t for t in all_tables if is_stat_table(t)]
    if not stat_tables:
        return [], []

    players = []
    totals  = []
    for team_idx, df in enumerate(stat_tables[:2]):  # only first 2 stat tables = 2 teams
        df.columns = [str(c).upper() for c in df.columns]
        for _, row in df.iterrows():
            name = str(row.get("PLAYER", row.iloc[0])).strip()
            if not name or name.upper() in ("STARTERS", "BENCH", "TOTALS", "TEAM", "NAN", "PLAYER"):
                continue
            fg = str(row.get("FG", "")).strip()
            if name.upper() == "TOTALS" or not re.search(r'\d', name):
                totals.append({"team_idx": team_idx, "fg": fg, "to": str(row.get("TO", "0"))})
                continue
            players.append({
                "team_idx": team_idx,
                "name":  name,
                "min":   str(row.get("MIN", "")),
                "pts":   str(row.get("PTS", "")),
                "fg":    fg,
                "3pt":   str(row.get("3PT", "")),
                "ft":    str(row.get("FT", "")),
                "reb":   str(row.get("REB", "")),
                "ast":   str(row.get("AST", "")),
                "to":    str(row.get("TO",  "")),
                "stl":   str(row.get("STL", "")),
                "blk":   str(row.get("BLK", "")),
            })
    return players, totals


def extract_players_from_divs(html):
    """Fallback for div/span grid layouts (v3) — find rows with 3+ FG patterns."""
    soup = BeautifulSoup(html, "html.parser")
    players = []
    team_idx = -1

    for el in soup.find_all(True):
        text = el.get_text(strip=True).upper()
        if text == "STARTERS":
            team_idx += 1
            continue
        children = [c.get_text(strip=True) for c in el.find_all(recursive=False) if c.get_text(strip=True)]
        if len(children) < 5:
            continue
        fg_count = sum(1 for c in children if re.match(r"^\d{1,2}-\d{1,2}$", c))
        if fg_count < 2:
            continue
        players.append({
            "team_idx": team_idx,
            "name":  children[0],
            "min":   children[1] if len(children) > 1 else "",
            "pts":   children[2] if len(children) > 2 else "",
            "fg":    children[3] if len(children) > 3 else "",
            "3pt":   children[4] if len(children) > 4 else "",
            "ft":    children[5] if len(children) > 5 else "",
            "reb":   children[6] if len(children) > 6 else "",
            "ast":   children[7] if len(children) > 7 else "",
            "to":    children[8] if len(children) > 8 else "",
            "stl":   children[9] if len(children) > 9 else "",
            "blk":   children[10] if len(children) > 10 else "",
        })
    return players, []


def extract_team_names(html):
    soup = BeautifulSoup(html, "html.parser")
    names = []
    for el in soup.find_all(["div", "span", "h1", "h2", "a"]):
        cls = " ".join(el.get("class", []))
        t = el.get_text(strip=True)
        if re.search(r"team.?name|TeamName|team.?title", cls, re.I):
            if t and len(t) > 3 and t not in names:
                names.append(t)
        if len(names) >= 2:
            break
    return names[:2]


def scrape_resilient(html: str) -> dict:
    players, totals = extract_players_from_tables(html)
    if not players:
        players, totals = extract_players_from_divs(html)
    return {
        "team_names": extract_team_names(html),
        "players":    players,
        "totals":     totals,
    }


def analyze(data: dict):
    players    = data["players"]
    team_names = data.get("team_names", [])

    for p in players:
        idx = p.get("team_idx", 0)
        p["team"] = team_names[idx] if idx < len(team_names) else f"Team {idx+1}"

    teams = {}
    for p in players:
        teams.setdefault(p["team"], []).append(p)

    team_stats = {}
    for team, roster in teams.items():
        total_tov = 0
        total_fg  = 0
        total_fga = 0
        for p in roster:
            try: total_tov += int(p.get("to") or 0)
            except: pass
            try:
                made, att = (p.get("fg") or "0-0").split("-")
                total_fg  += int(made)
                total_fga += int(att)
            except: pass
        team_stats[team] = {"tov": total_tov, "fg_pct": total_fg / total_fga if total_fga else 0}

    if len(team_stats) < 2:
        return "Not enough data", [], team_stats

    advantage_team = min(team_stats, key=lambda t: (team_stats[t]["tov"], -team_stats[t]["fg_pct"]))
    adv = team_stats[advantage_team]
    advantage_str = f"{advantage_team} (TOV: {adv['tov']}, FG%: {adv['fg_pct']:.1%})"

    player_scores = []
    for p in players:
        try:
            tov = int(p.get("to") or 0)
            made, att = (p.get("fg") or "0-0").split("-")
            fg_pct = int(made) / int(att) if int(att) > 0 else 0
            player_scores.append({"player": p["name"], "team": p["team"], "tov": tov, "fg_pct": fg_pct, "score": fg_pct - tov * 0.05})
        except:
            continue

    top_props = sorted(player_scores, key=lambda x: x["score"], reverse=True)[:3]
    return advantage_str, top_props, team_stats


def send_discord(data: dict):
    now = datetime.now().strftime("%b %d %Y %I:%M %p")
    advantage_str, top_props, team_stats = analyze(data)
    team_names = data.get("team_names", ["Team 1", "Team 2"])

    body  = f"**NCAA Championship — {' vs '.join(team_names)}**\n`{now}`\n"
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