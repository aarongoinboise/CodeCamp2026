"""
DEMO 2 — Getting Blocked → Getting Around It
Part A: naive requests call → 403
Part B: Playwright with stealth → scrapes the page directly → sends Discord message with stats
"""

import asyncio
import re
from bs4 import BeautifulSoup
import random
from datetime import datetime
import os
import requests
from playwright.async_api import async_playwright
from dotenv import load_dotenv
load_dotenv()

URL = "https://www.espn.com/mens-college-basketball/boxscore/_/gameId/401856600"
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")


# ── Part A: Naive — gets blocked ─────────────────────────────────────────────

def naive_scrape():
    print(f"\n  URL: {URL}")
    print("  No headers. No browser. No JavaScript execution.\n")

    response = requests.get(URL, timeout=10)

    print(f"  Status code  : {response.status_code}")
    print(f"  Body length  : {len(response.text)} chars")

    if response.status_code == 403:
        print("\n  ⛔  403 FORBIDDEN — blocked by CloudFront CDN")
        print("      ESPN never even saw this request.")
        print("      CloudFront fingerprinted us as a bot at the network edge.")
        print("\n      Run with --evade to see how Playwright gets through.\n")
        return

    print("\n  ⚠  200 OK but page is a blank React shell — no data without JS.\n")


# ── Part B: Playwright — loads the real page, parses the DOM ─────────────────

async def evade_and_scrape():
    print(f"\n  URL: {URL}")
    print("  Launching Chromium...\n")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
            ]
        )

        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1440, "height": 900},
            locale="en-US",
            timezone_id="America/New_York",
            extra_http_headers={
                "Accept-Language": "en-US,en;q=0.9",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            }
        )

        page = await context.new_page()

        await page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => false });
            Object.defineProperty(navigator, 'plugins',   { get: () => [1, 2, 3] });
            Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
        """)

        print("  Navigating to ESPN...")
        await page.goto(URL, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(random.uniform(3, 5))

        html = await page.content()
        await browser.close()

    print("  ✓  Page loaded, parsing...\n")

    soup = BeautifulSoup(html, "html.parser")
    all_rows = []
    headers = ["MIN", "PTS", "FG", "3PT", "FT", "REB", "AST", "TO", "STL", "BLK", "OREB", "DREB", "PF"]

    titles = soup.select("div.Boxscore__Title")
    sections = soup.select("div.ResponsiveTable")

    for title, section in zip(titles, sections):
        team_name = title.select_one("div.BoxscoreItem__TeamName").get_text(strip=True)
        tables = section.find_all("table")
        name_table = next((t for t in tables if t.find("a", href=lambda h: h and "/player/" in h)), None)
        stat_table = next((t for t in tables if t.find(string=re.compile(r"^\d+-\d+$"))), None)
        if not name_table or not stat_table:
            continue

        names = []
        for row in name_table.find_all("tr"):
            a = row.find("a", href=lambda h: h and "/player/" in h)
            if a:
                long_name = a.find("span", class_=lambda c: c and "long" in c)
                names.append(long_name.get_text(strip=True) if long_name else a.get_text(strip=True))

        player_rows = []
        for row in stat_table.find_all("tr"):
            cells = row.find_all("td")
            values = [c.get_text(strip=True) for c in cells]
            if len(values) != 13 or not re.match(r"^\d+-\d+$", values[2]):
                continue
            player_rows.append(values)

        for name, values in zip(names, player_rows):
            record = dict(zip(headers, values))
            record["player"] = name
            record["team"] = team_name
            all_rows.append(record)
            print(f"  {team_name[:6]} {name[:22]:<22}  "
                  f"MIN={record.get('MIN', '?'):>3}  PTS={record.get('PTS', '?'):>3}  "
                  f"FG={record.get('FG', '?'):>5}  TO={record.get('TO', '?'):>2}")

    print(f"\n  ✓  {len(all_rows)} players parsed")
    advantage_str, top_props, team_stats = analyze(all_rows)
    send_discord(advantage_str, top_props, team_stats)


# ── Analysis ──────────────────────────────────────────────────────────────────

def analyze(rows):
    teams = {}
    for row in rows:
        teams.setdefault(row["team"], []).append(row)

    team_stats = {}
    for team, players in teams.items():
        total_tov = sum(int(p.get("TO", 0) or 0) for p in players if str(p.get("TO", "")).isdigit())
        fg_parts = [p.get("FG", "0-0").split("-") for p in players if "-" in p.get("FG", "")]
        total_fg = sum(int(m) for m, a in fg_parts)
        total_fga = sum(int(a) for m, a in fg_parts)
        fg_pct = total_fg / total_fga if total_fga else 0
        team_stats[team] = {"tov": total_tov, "fg_pct": fg_pct}

    keys = list(team_stats.keys())
    if len(keys) < 2:
        return "Not enough data", [], team_stats
    t1, t2 = keys[0], keys[1]

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
        try:
            tov = int(row.get("TO", 0) or 0)
            fg_str = row.get("FG", "0-0") or "0-0"
            made, att = fg_str.split("-")
            fg_pct = int(made) / int(att) if int(att) > 0 else 0
            player_scores.append({
                "player": row["player"],
                "team": row["team"],
                "tov": tov,
                "fg_pct": fg_pct,
                "score": fg_pct - (tov * 0.05),
            })
        except:
            continue

    top_props = sorted(player_scores, key=lambda x: x["score"], reverse=True)[:3]
    return advantage_str, top_props, team_stats


# ── Send Discord ──────────────────────────────────────────────────────────────

def send_discord(advantage_str, top_props, team_stats):
    now = datetime.now().strftime("%b %d %Y %I:%M %p")

    body = f"**NCAA Championship — Michigan vs UConn**\n`{now}`\n"
    body += f"\n**ADVANTAGE:** {advantage_str}\n"
    body += "\n**TEAM TOTALS**\n"
    for team, stats in team_stats.items():
        body += f"{team}: TOV {stats['tov']}  FG% {stats['fg_pct']:.1%}\n"
    body += "\n**TOP PROPS**\n"
    for p in top_props:
        body += f"{p['player']} ({p['team']})  FG% {p['fg_pct']:.1%}  TOV {p['tov']}\n"

    requests.post(DISCORD_WEBHOOK, json={"content": body})
    print("  ✓  Discord message sent.")