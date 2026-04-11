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

    # SR boxscores have two tables — one per team
    # They're usually buried in HTML comments
    import re
    comments = soup.find_all(string=lambda t: isinstance(t, str) and "basic" in t)

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
        # Derive team name from table id e.g. "box-michigan-game-basic"
        parts = tid.replace("box-", "").replace("-game-basic", "").replace("-basic", "")
        team_name = parts.replace("-", " ").title()
        players = parse_table(table, team_name)
        all_players.extend(players)

    return all_players


def parse_table(table, team_name):
    players = []
    headers = []

    thead = table.find("thead")
    if thead:
        for th in thead.find_all("th"):
            headers.append(th.get("data-stat", th.text.strip()))

    tbody = table.find("tbody")
    if not tbody:
        return players

    for row in tbody.find_all("tr"):
        if "class" in row.attrs and "thead" in row["class"]:
            continue
        if not row.find("td"):
            continue
        cells = row.find_all(["th", "td"])
        player = {"team": team_name}
        for i, cell in enumerate(cells):
            key = headers[i] if i < len(headers) else f"col_{i}"
            player[key] = cell.text.strip()
        name = player.get("player") or player.get("name_display", "")
        if name and name.lower() not in ("reserves", "team totals", ""):
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

    now = datetime.now().strftime("%b %d %Y %I:%M %p")
    th_cells = "".join(f"<th>{h}</th>" for h in headers)

    # Group by team
    teams = {}
    for row in rows:
        team = row.get("team", "Unknown")
        teams.setdefault(team, []).append(row)

    body = ""
    for team, players in teams.items():
        body += f'<tr><td colspan="{len(headers)}" style="background:#ddd;font-weight:bold;padding:6px 8px;">{team}</td></tr>\n'
        for row in players:
            td_cells = "".join(f"<td>{row.get(h, '')}</td>" for h in headers)
            body += f"<tr>{td_cells}</tr>\n"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>2026 NCAA Championship Boxscore</title>
<style>
  body {{
    font-family: Arial, sans-serif;
    font-size: 13px;
    padding: 10px;
    background: #fff;
    color: #000;
  }}
  h2 {{ margin: 0 0 4px 0; }}
  p  {{ margin: 0 0 10px 0; color: #555; font-size: 11px; }}
  table {{ border-collapse: collapse; width: 100%; }}
  th, td {{
    border: 1px solid #ccc;
    padding: 5px 8px;
    text-align: left;
    white-space: nowrap;
  }}
  th {{ background: #f0f0f0; font-weight: bold; }}
  tr:nth-child(even) {{ background: #f9f9f9; }}
  tr:hover {{ background: #fffbcc; }}
</style>
</head>
<body>
<h2>2026 NCAA Championship — Michigan vs UConn</h2>
<p>Last updated: {now} · Re-run script to refresh</p>
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

# ── Job ──────────────────────────────────────────────────────────────────────

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
    job()
    schedule.every(5).minutes.do(job)
    print("Running every 5 minutes. Press CTRL+C to stop.")
    while True:
        schedule.run_pending()
        time.sleep(1)