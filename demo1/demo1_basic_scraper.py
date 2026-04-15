import requests
from bs4 import BeautifulSoup
from datetime import datetime
import schedule
import time
import argparse
import os
import smtplib
from email.mime.text import MIMEText

# ── Config ────────────────────────────────────────────────────────────────────
BOXSCORE_URL = "https://www.sports-reference.com/cbb/boxscores/2026-04-06-20-michigan.html"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.sports-reference.com/cbb/",
}

# ── Scraper ───────────────────────────────────────────────────────────────────

def get_boxscore(url):
    print(f"Fetching: {url}")
    response = requests.get(url, headers=HEADERS, timeout=15)
    if response.status_code != 200:
        print(f"Got status {response.status_code}. Exiting.")
        return []
    print(f"Status: {response.status_code} OK")

    soup = BeautifulSoup(response.text, "html.parser")
    all_players = []

    tables_found = []
    for table in soup.find_all("table"):
        tid = table.get("id", "")
        if "basic" in tid and "box" in tid:
            tables_found.append((tid, table))

    for tid, table in tables_found:
        print(tid)
        team_name = (
            tid.replace("box", "")
               .replace("-score", "")
               .replace("-game-basic", "")
               .replace("-basic", "")
               .replace("-", "")
               .title()
        )
        print(team_name)
        players = parse_table(table, team_name)
        all_players.extend(players)

    return all_players


def parse_table(table, team_name):
    players = []
    headers = []
    thead = table.find("thead")
    if thead:
        header_rows = thead.find_all("tr")
        last_header_row = header_rows[-1]
        for th in last_header_row.find_all("th"):
            headers.append(th.get("data-stat", "").strip())

    tbody = table.find("tbody")
    if not tbody:
        return players

    for row in tbody.find_all("tr"):
        if "class" in row.attrs and "thead" in row.attrs["class"]:
            continue
        if not row.find("td"):
            continue

        cells = row.find_all(["th", "td"])
        player = {"team": team_name}
        for i, cell in enumerate(cells):
            key = headers[i] if i < len(headers) else f"col_{i}"
            if not key:
                continue
            player[key] = cell.text.strip()

        name = player.get("player", "")
        if not name or name.lower() in ("reserves", "team totals", ""):
            continue

        players.append(player)

    return players


# ── Analysis ──────────────────────────────────────────────────────────────────

def analyze(rows):
    teams = {}
    for row in rows:
        team = row.get("team", "Unknown")
        teams.setdefault(team, []).append(row)

    team_stats = {}
    for team, players in teams.items():
        total_tov = 0
        total_fg  = 0
        total_fga = 0
        for p in players:
            try: total_tov += int(p.get("tov", 0) or 0)
            except: pass
            try: total_fg  += int(p.get("fg",  0) or 0)
            except: pass
            try: total_fga += int(p.get("fga", 0) or 0)
            except: pass
        fg_pct = total_fg / total_fga if total_fga else 0
        team_stats[team] = {"tov": total_tov, "fg_pct": fg_pct}

    sorted_by_tov   = sorted(team_stats, key=lambda t: team_stats[t]["tov"])
    sorted_by_fgpct = sorted(team_stats, key=lambda t: team_stats[t]["fg_pct"], reverse=True)

    scores = {t: 0 for t in team_stats}
    for rank, t in enumerate(sorted_by_tov):
        scores[t] += rank
    for rank, t in enumerate(sorted_by_fgpct):
        scores[t] += (len(team_stats) - 1 - rank)

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
    for row in rows:
        name = row.get("player", "")
        if not name:
            continue
        try:
            tov    = int(row.get("tov", 0) or 0)
            fg     = int(row.get("fg",  0) or 0)
            fga    = int(row.get("fga", 0) or 0)
            fg_pct = fg / fga if fga > 0 else 0
            score  = fg_pct - (tov * 0.05)
            player_scores.append({
                "player": name,
                "team":   row.get("team", ""),
                "tov":    tov,
                "fg_pct": fg_pct,
                "score":  score,
            })
        except:
            continue

    top_props = sorted(player_scores, key=lambda x: x["score"], reverse=True)[:3]

    return advantage_str, top_props, team_stats


# ── Send Email ────────────────────────────────────────────────────────────────

def send_email(advantage_str, top_props, team_stats):
    now = datetime.now().strftime("%b %d %Y %I:%M %p")

    body = f"2026 NCAA Championship — Michigan vs UConn\nLast updated: {now}\n"
    body += "=" * 40 + "\n\n"

    body += f"ADVANTAGE: {advantage_str}\n"
    body += "Based on fewest turnovers and highest field goal percentage.\n\n"

    body += "TEAM TOTALS\n"
    body += "-" * 30 + "\n"
    for team, stats in team_stats.items():
        body += f"{team}: TOV: {stats['tov']}  FG%: {stats['fg_pct']:.1%}\n"

    body += "\nTOP PROPS — Best FG% & Fewest Turnovers\n"
    body += "-" * 30 + "\n"
    for p in top_props:
        body += f"{p['player']} ({p['team']})  FG%: {p['fg_pct']:.1%}  TOV: {p['tov']}\n"

    msg = MIMEText(body)
    msg["Subject"] = f"Game Update — {now}"
    msg["From"]    = os.environ.get("GMAIL_USER")
    msg["To"]      = os.environ.get("GMAIL_USER")

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(os.environ.get("GMAIL_USER"), os.environ.get("GMAIL_APP_PASSWORD"))
        server.send_message(msg)
    print("Email sent.")


# ── Job ───────────────────────────────────────────────────────────────────────

def job():
    players = get_boxscore(BOXSCORE_URL)
    if players:
        advantage_str, top_props, team_stats = analyze(players)
        send_email(advantage_str, top_props, team_stats)
    else:
        print("No data found.")


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--schedule", action="store_true", help="Run every 5 minutes")
    args = parser.parse_args()

    job()

    if args.schedule:
        schedule.every(5).minutes.do(job)
        print("Running every 5 minutes. Press CTRL+C to stop.")
        while True:
            schedule.run_pending()
            time.sleep(1)