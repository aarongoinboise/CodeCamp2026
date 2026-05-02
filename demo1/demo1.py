import requests
from bs4 import BeautifulSoup
import os
from util import analyze, send_discord
from dotenv import load_dotenv
load_dotenv()


# ── Config ────────────────────────────────────────────────────────────────────

BOXSCORE_URL = "https://www.sports-reference.com/cbb/boxscores/2026-04-06-20-michigan.html"
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")

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


# ── Job ───────────────────────────────────────────────────────────────────────

def job():
    players = get_boxscore(BOXSCORE_URL)
    if players:
        advantage_str, top_props, team_stats = analyze(players)
        send_discord(advantage_str, top_props, team_stats)
    else:
        print("No data found.")