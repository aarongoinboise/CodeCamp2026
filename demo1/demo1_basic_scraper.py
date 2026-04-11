"""
Scrapes a specific game boxscore from sports-reference.com
→ saves CSV → saves a plain HTML table → pushes to GitHub

INSTALL:
  pip install requests beautifulsoup4

RUN:
  python demo1_basic_scraper.py
"""

import requests
from bs4 import BeautifulSoup
import csv
import subprocess
from datetime import datetime
import schedule
import time
import argparse

# ── Config ────────────────────────────────────────────────────────────────────
BOXSCORE_URL = "https://www.sports-reference.com/cbb/boxscores/2026-04-06-20-michigan.html"
OUTPUT_CSV   = "player_stats.csv"
OUTPUT_HTML  = "dashboard.html"

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

    # SR buries tables in HTML comments — parse them out
    from bs4 import Comment
    comments = soup.find_all(string=lambda t: isinstance(t, Comment))

    tables_found = []
    for comment in comments:
        comment_soup = BeautifulSoup(comment, "html.parser")
        for table in comment_soup.find_all("table"):
            tid = table.get("id", "")
            if "basic" in tid and "box" in tid:
                tables_found.append((tid, table))

    # Fallback: visible tables
    if not tables_found:
        for table in soup.find_all("table"):
            tid = table.get("id", "")
            if "basic" in tid and "box" in tid:
                tables_found.append((tid, table))

    for tid, table in tables_found:
        # table id format: "box-connecticut-game-basic" or "box-michigan-game-basic"
        team_name = (
            tid.replace("box-", "")
               .replace("-game-basic", "")
               .replace("-basic", "")
               .replace("-", " ")
               .title()
        )
        players = parse_table(table, team_name)
        all_players.extend(players)

    return all_players


def parse_table(table, team_name):
    players = []

    # Get headers from data-stat attributes — these are the clean column keys
    headers = []
    thead = table.find("thead")
    if thead:
        # Use the last header row (some tables have two header rows)
        header_rows = thead.find_all("tr")
        last_header_row = header_rows[-1]
        for th in last_header_row.find_all("th"):
            headers.append(th.get("data-stat", "").strip())

    tbody = table.find("tbody")
    if not tbody:
        return players

    for row in tbody.find_all("tr"):
        # Skip separator/header rows inside tbody
        if "class" in row.attrs and "thead" in row.attrs["class"]:
            continue
        if not row.find("td"):
            continue

        cells = row.find_all(["th", "td"])
        player = {"team": team_name.replace("Score ", "")}
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


# ── Save CSV ──────────────────────────────────────────────────────────────────

def save_csv(data, filename):
    if not data:
        print("No data to save.")
        return
    clean = [{k: v for k, v in row.items() if k} for row in data]
    all_keys = list(clean[0].keys())
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=all_keys, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(clean)
    print(f"CSV saved -> {filename}")


# ── Analysis ──────────────────────────────────────────────────────────────────

def analyze(rows):
    # Group by team
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

    # Score: lower turnovers + higher FG% wins
    # Normalize: give each team a score — lower TOV rank + higher FG% rank
    sorted_by_tov   = sorted(team_stats, key=lambda t: team_stats[t]["tov"])
    sorted_by_fgpct = sorted(team_stats, key=lambda t: team_stats[t]["fg_pct"], reverse=True)

    scores = {t: 0 for t in team_stats}
    for rank, t in enumerate(sorted_by_tov):
        scores[t] += rank        # lower = better
    for rank, t in enumerate(sorted_by_fgpct):
        scores[t] += (len(team_stats) - 1 - rank)  # higher FG% = better score

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

    # Best props: players with fewest TOV and best FG%
    # Combined score: fg_pct - (tov * 0.05) — penalize turnovers
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


# ── Save HTML from CSV ────────────────────────────────────────────────────────

def save_html_from_csv(csv_file, html_file):
    rows = []
    with open(csv_file, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames or []
        for row in reader:
            rows.append(row)

    if not rows:
        print("CSV is empty, skipping HTML.")
        return

    advantage_str, top_props, team_stats = analyze(rows)
    team_stats_rows = ""
    for team, stats in team_stats.items():
        team_stats_rows += (
            f"<tr><td>{team}</td><td>{stats['tov']}</td><td>{stats['fg_pct']:.1%}</td></tr>\n"
        )

    now = datetime.now().strftime("%b %d %Y %I:%M %p")
    th_cells = "".join(f"<th>{h}</th>" for h in headers)

    # Group by team, split starters/bench by mp (starters played more)
    teams = {}
    for row in rows:
        team = row.get("team", "Unknown")
        teams.setdefault(team, []).append(row)

    body = ""
    for team, players in teams.items():
        body += f'<tr class="team-header"><td colspan="{len(headers)}">{team}</td></tr>\n'
        for row in players:
            td_cells = "".join(f"<td>{row.get(h, '')}</td>" for h in headers)
            body += f"<tr>{td_cells}</tr>\n"

    props_rows = ""
    for p in top_props:
        props_rows += (
            f"<tr>"
            f"<td>{p['player']}</td>"
            f"<td>{p['team']}</td>"
            f"<td>{p['fg_pct']:.1%}</td>"
            f"<td>{p['tov']}</td>"
            f"</tr>\n"
        )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>2026 NCAA Championship Boxscore</title>
<style>
  body {{ font-family: Arial, sans-serif; font-size: 13px; padding: 10px; background: #fff; color: #000; }}
  h2   {{ margin: 0 0 4px 0; }}
  h3   {{ margin: 16px 0 6px 0; font-size: 14px; }}
  p    {{ margin: 0 0 10px 0; color: #555; font-size: 11px; }}
  table {{ border-collapse: collapse; width: 100%; margin-bottom: 24px; }}
  th, td {{ border: 1px solid #ccc; padding: 5px 8px; text-align: left; white-space: nowrap; }}
  th {{ background: #f0f0f0; font-weight: bold; }}
  tr:nth-child(even) {{ background: #f9f9f9; }}
  tr:hover {{ background: #fffbcc; }}
  tr.team-header td {{ background: #002d62; color: #fff; font-weight: bold; font-size: 14px; padding: 8px; }}
  .advantage {{ background: #e8f5e9; border: 1px solid #a5d6a7; padding: 10px 14px; border-radius: 4px; margin-bottom: 16px; font-size: 14px; }}
  .advantage strong {{ color: #1b5e20; }}
  .props {{ background: #fff8e1; border: 1px solid #ffe082; padding: 10px 14px; border-radius: 4px; margin-bottom: 16px; }}
  .props h3 {{ margin: 0 0 8px 0; color: #e65100; }}
</style>
</head>
<body>
<h2>2026 NCAA Championship — Michigan vs UConn</h2>
<p>Last updated: {now} · Re-run script to refresh</p>

<div class="advantage">
  <strong>Advantage: {advantage_str}</strong><br>
  Based on fewest turnovers and highest field goal percentage.
</div>

<div class="props">
  <h3>Team Totals</h3>
  <table>
    <thead><tr><th>Team</th><th>Turnovers</th><th>FG%</th></tr></thead>
    <tbody>{team_stats_rows}</tbody>
  </table>
</div>

<div class="props">
  <h3>Possible Props — Best Combined FG% &amp; Fewest Turnovers</h3>
  <table>
    <thead><tr><th>Player</th><th>Team</th><th>FG%</th><th>TOV</th></tr></thead>
    <tbody>{props_rows}</tbody>
  </table>
</div>

<h3>Full Box Score</h3>
<div style="overflow-x:auto">
<table>
  <thead><tr>{th_cells}</tr></thead>
  <tbody>{body}</tbody>
</table>
</div>
</body>
</html>"""

    with open(html_file, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"HTML saved -> {html_file}")


# ── Push to GitHub ────────────────────────────────────────────────────────────

def push_to_github():
    try:
        subprocess.run(["git", "add", "dashboard.html", "player_stats.csv"], check=True)
        subprocess.run(["git", "commit", "-m", f"refresh {datetime.now().strftime('%Y-%m-%d %H:%M')}"], check=True)
        subprocess.run(["git", "push"], check=True)
        print("Pushed to GitHub.")
    except subprocess.CalledProcessError as e:
        print(f"Git push failed: {e}")


# ── Job ───────────────────────────────────────────────────────────────────────

def job():
    players = get_boxscore(BOXSCORE_URL)
    if players:
        save_csv(players, OUTPUT_CSV)
        save_html_from_csv(OUTPUT_CSV, OUTPUT_HTML)
        push_to_github()
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