import os
import json
import requests
from google import genai
from bs4 import BeautifulSoup
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()

# https://aistudio.google.com/

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")
V1_URL   = "https://aarongoinboise.github.io/CodeCamp2026/demo3/v1.html"
V2_URL   = "https://aarongoinboise.github.io/CodeCamp2026/demo3/v2.html"
V3_URL   = "https://aarongoinboise.github.io/CodeCamp2026/demo3/v3.html"
ESPN_URL = "https://www.espn.com/mens-college-basketball/boxscore/_/gameId/401856600"


def fetch_text(url):
    headers = {"User-Agent": "Mozilla/5.0"}
    resp = requests.get(url, headers=headers, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    return soup.get_text(separator="\n", strip=True)


def extract_with_ai(text):
    prompt = f"""
From this basketball box score page text, extract:
- Both team names
- Each player's: name, team, MIN, PTS, FG, 3PT, FT, REB, AST, TO, STL, BLK

Rules:
- Player name should be the full name only, no abbreviated version appended
- Only include players who actually played (have a MIN value)
- team field must exactly match one of the two team names
- make absolutely sure each player is assigned to the correct team they play for
- Team B players must be assigned to Team B, not Team A

Return JSON only, no markdown:
{{
  "team_names": ["Team A", "Team B"],
  "players": [
    {{"name": "Player Name", "team": "Team A", "min": "32", "pts": "14", "fg": "5-10", "3pt": "2-4", "ft": "2-2", "reb": "4", "ast": "3", "to": "1", "stl": "0", "blk": "0"}}
  ]
}}

TEXT:
{text[:25000]}
"""
    res = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
    raw = res.text.strip().replace("```json", "").replace("```", "")
    return json.loads(raw)


def analyze(data):
    players    = data["players"]
    team_names = data["team_names"]

    teams = {}
    for p in players:
        teams.setdefault(p["team"], []).append(p)

    team_stats = {}
    for team, roster in teams.items():
        tov = 0
        fg  = 0
        fga = 0
        for p in roster:
            try: tov += int(p.get("to") or 0)
            except: pass
            try:
                m, a = (p.get("fg") or "0-0").split("-")
                fg += int(m); fga += int(a)
            except: pass
        team_stats[team] = {"tov": tov, "fg_pct": fg / fga if fga else 0}

    if len(team_stats) < 2:
        return "Not enough data", [], team_stats

    advantage_team = min(team_stats, key=lambda t: (team_stats[t]["tov"], -team_stats[t]["fg_pct"]))
    adv = team_stats[advantage_team]
    advantage_str = f"{advantage_team} (TOV: {adv['tov']}, FG%: {adv['fg_pct']:.1%})"

    player_scores = []
    for p in players:
        try:
            tov = int(p.get("to") or 0)
            m, a = (p.get("fg") or "0-0").split("-")
            fg_pct = int(m) / int(a) if int(a) > 0 else 0
            player_scores.append({
                "player": p["name"],
                "team":   p["team"],
                "tov":    tov,
                "fg_pct": fg_pct,
                "score":  fg_pct - tov * 0.05
            })
        except: continue

    sorted_players = sorted(player_scores, key=lambda x: x["score"], reverse=True)
    top_props = []
    if sorted_players:
        cutoff = sorted_players[min(2, len(sorted_players)-1)]["score"]
        top_props = [p for p in sorted_players if p["score"] >= cutoff]
    return advantage_str, top_props, team_stats


def send_discord(data, source):
    now = datetime.now().strftime("%b %d %Y %I:%M %p")
    advantage_str, top_props, team_stats = analyze(data)
    team_names = data["team_names"]

    body  = f"{source}\n\n"
    body += f"**NCAA Championship — {' vs '.join(team_names)}**\n"
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


def run(url):
    text = fetch_text(url)
    data = extract_with_ai(text)
    send_discord(data, url)

def run_v1():   run(V1_URL)
def run_v2():   run(V2_URL)
def run_v3():   run(V3_URL)
def run_espn(): run(ESPN_URL)