"""
Scrapes player stats → saves CSV → saves a plain HTML table you can open on your phone.
Re-run to refresh.

INSTALL:
  pip install requests beautifulsoup4

RUN:
  python demo1_basic_scraper.py
"""

import requests
from bs4 import BeautifulSoup
import csv
import time
import sys
from datetime import datetime
from pyngrok import ngrok

# ── Config ────────────────────────────────────────────────────────────────────
BASE_URL      = "https://www.sports-reference.com"
TEAM_SLUG     = "kansas"
SEASON        = "2024"
OUTPUT_CSV    = "player_stats.csv"
OUTPUT_HTML   = "dashboard.html"

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

def get_team_stats(team_slug, season):
    url = f"{BASE_URL}/cbb/schools/{team_slug}/{season}.html"
    print(f"Fetching: {url}")
    response = requests.get(url, headers=HEADERS, timeout=15)
    if response.status_code != 200:
        print(f"Got status {response.status_code}. Exiting.")
        sys.exit(1)
    print(f"Status: {response.status_code} OK")
    soup = BeautifulSoup(response.text, "html.parser")

    players = []

    # SR hides tables in HTML comments — check there first
    comments = soup.find_all(string=lambda t: isinstance(t, str) and "per_game" in t)
    for comment in comments:
        comment_soup = BeautifulSoup(comment, "html.parser")
        table = comment_soup.find("table", {"id": "per_game"})
        if table:
            players = parse_table(table)
            break

    if not players:
        table = soup.find("table", {"id": "per_game"})
        if table:
            players = parse_table(table)

    if not players:
        for t in soup.find_all("table"):
            if len(t.find_all("tr")) > 5:
                players = parse_table_generic(t)
                if players:
                    break

    return players


def parse_table(table):
    players = []
    headers = []
    thead = table.find("thead")
    if thead:
        for th in thead.find_all("th"):
            headers.append(th.get("data-stat", th.text.strip()))
    for row in table.find("tbody").find_all("tr"):
        if "class" in row.attrs and "thead" in row["class"]:
            continue
        if not row.find("td"):
            continue
        cells = row.find_all(["th", "td"])
        player = {}
        for i, cell in enumerate(cells):
            key = headers[i] if i < len(headers) else f"col_{i}"
            player[key] = cell.text.strip()
        if player.get("player") or player.get("name_display"):
            players.append(player)
    return players


def parse_table_generic(table):
    rows = table.find_all("tr")
    if not rows:
        return []
    headers = [c.text.strip() for c in rows[0].find_all(["th", "td"])]
    if not any(headers):
        return []
    players = []
    for row in rows[1:]:
        cells = row.find_all(["th", "td"])
        if not cells:
            continue
        players.append({headers[i]: cells[i].text.strip()
                        for i in range(min(len(headers), len(cells)))})
    return players


# ── Save CSV ──────────────────────────────────────────────────────────────────

def save_csv(data, filename):
    if not data:
        print("No data to save.")
        return
    clean = [{k: v for k, v in row.items() if k} for row in data]
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(clean[0].keys()), extrasaction="ignore")
        writer.writeheader()
        writer.writerows(clean)
    print(f"CSV saved -> {filename}")


# ── Save HTML (reads directly from CSV so columns always match) ───────────────

def save_html_from_csv(csv_file, html_file, team, season):
    """Read the CSV we just wrote and turn it into a plain HTML table."""
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

    tr_rows = ""
    for row in rows:
        td_cells = "".join(f"<td>{row.get(h, '')}</td>" for h in headers)
        tr_rows += f"<tr>{td_cells}</tr>\n"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{team.title()} {season} Stats</title>
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
  table {{
    border-collapse: collapse;
    width: 100%;
  }}
  th, td {{
    border: 1px solid #ccc;
    padding: 5px 8px;
    text-align: left;
    white-space: nowrap;
  }}
  th {{
    background: #f0f0f0;
    font-weight: bold;
  }}
  tr:nth-child(even) {{ background: #f9f9f9; }}
  tr:hover {{ background: #fffbcc; }}
</style>
</head>
<body>
<h2>{team.title()} — {season} Per-Game Stats</h2>
<p>Last updated: {now} · Re-run script to refresh</p>
<div style="overflow-x:auto">
<table>
  <thead><tr>{th_cells}</tr></thead>
  <tbody>{tr_rows}</tbody>
</table>
</div>
</body>
</html>"""

    with open(html_file, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"HTML saved -> {html_file}")


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    players = get_team_stats(TEAM_SLUG, SEASON)
    if players:
        print(f"Found {len(players)} players.")
        save_csv(players, OUTPUT_CSV)
        save_html_from_csv(OUTPUT_CSV, OUTPUT_HTML, TEAM_SLUG, SEASON)
        url = ngrok.connect(8080)
        print(f"Open on your phone: {url}")
    else:
        print("No player data found.")
    time.sleep(1)