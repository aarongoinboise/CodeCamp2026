"""
DEMO 2 — Getting Blocked → Getting Around It
Part A: naive requests call → 403
Part B: Playwright with stealth → scrapes the page directly → sends Discord message with stats
"""

import asyncio
import random
from datetime import datetime
import os
from bs4 import BeautifulSoup
import requests
from playwright.async_api import async_playwright
from dotenv import load_dotenv
load_dotenv()

URL = "https://www.espn.com/mens-college-basketball/boxscore/_/gameId/401856600"
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")
STAT_HEADERS = ["MIN", "PTS", "FG", "3PT", "FT", "REB", "AST", "TO", "STL", "BLK", "OREB", "DREB", "PF"]


# ── Part A: Naive — gets blocked ─────────────────────────────────────────────

def naive_scrape():
    print(f"\n  URL: {URL}")
    print("  No headers. No browser. No JavaScript execution.\n")
    response = requests.get(URL, timeout=10)
    print(f"  Status code  : {response.status_code}")
    print(f"  Body length  : {len(response.text)} chars")
    if response.status_code == 403:
        print("\n  ⛔  403 FORBIDDEN — blocked by CloudFront CDN")
        print("      Run with --evade to see how Playwright gets through.\n")


# ── Part B: Playwright — loads the real page, parses the DOM ─────────────────

async def evade_and_scrape():
    print(f"\n  URL: {URL}")
    print("  Launching Chromium...\n")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"]
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
        )
        await context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', { get: () => false });"
        )

        page = await context.new_page()
        await page.goto(URL, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(random.uniform(3, 5))
        html = await page.content()
        await browser.close()

    print("  ✓  Page loaded, parsing...\n")
    soup = BeautifulSoup(html, "html.parser")
    all_rows = []

    for section in soup.find_all("table"):
        rows = section.find_all("tr")
        if not rows:
            continue

        col_count = len(rows[0].find_all(["td", "th"]))

        if col_count == 1:
            name_table = section
        elif col_count == 13:
            stat_table = section

            names = [row.get_text(strip=True) for row in name_table.find_all("tr") if row.get_text(strip=True)]
            stats = [
                [td.get_text(strip=True) for td in row.find_all("td")]
                for row in stat_table.find_all("tr")
                if len(row.find_all("td")) == 13
            ]
            team = "Team 1" if not all_rows else "Team 2"

            for name, values in zip(names, stats):
                record = {"player": name, "team": team, **dict(zip(STAT_HEADERS, values))}
                all_rows.append(record)
                print(f"  {team} {name[:22]:<22}  "
                      f"MIN={record['MIN']:>3}  PTS={record['PTS']:>3}  "
                      f"FG={record['FG']:>5}  TO={record['TO']:>2}")

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
        total_tov = sum(int(p["TO"]) for p in players if p.get("TO", "").isdigit())
        fg_parts = [p["FG"].split("-") for p in players if "-" in p.get("FG", "")]
        total_fg = sum(int(m) for m, a in fg_parts)
        total_fga = sum(int(a) for m, a in fg_parts)
        team_stats[team] = {
            "tov": total_tov,
            "fg_pct": total_fg / total_fga if total_fga else 0
        }

    advantage_team = min(team_stats, key=lambda t: (team_stats[t]["tov"], -team_stats[t]["fg_pct"]))
    adv = team_stats[advantage_team]
    advantage_str = f"{advantage_team} (TOV: {adv['tov']}, FG%: {adv['fg_pct']:.1%})"

    top_props = sorted(
        [{"player": p["player"], "team": p["team"],
          "tov": int(p["TO"]) if p.get("TO", "").isdigit() else 0,
          "fg_pct": int(p["FG"].split("-")[0]) / int(p["FG"].split("-")[1])
                   if "-" in p.get("FG", "") and int(p["FG"].split("-")[1]) > 0 else 0}
         for p in rows],
        key=lambda x: x["fg_pct"] - x["tov"] * 0.05,
        reverse=True
    )[:3]

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