import asyncio
import random
from datetime import datetime
import os
import requests
import pandas as pd
import re
import io
from playwright.async_api import async_playwright
from dotenv import load_dotenv
from util import analyze, send_discord
load_dotenv()

URL = "https://www.espn.com/mens-college-basketball/boxscore/_/gameId/401856600"
DISCORD_WEBHOOK_2 = os.getenv("DISCORD_WEBHOOK")
GENERAL_WEBHOOK = os.getenv("GENERAL_WEBHOOK")
STAT_HEADERS = ["MIN", "PTS", "FG", "3PT", "FT", "REB", "AST", "TO", "STL", "BLK", "OREB", "DREB", "PF"]
TOV_MULT = 0.05
JUNK = {"starters", "bench", "team"}

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


# ── Part B: Playwright — loads the real page, parses through HTML ─────────────────

async def evade_and_scrape(at=False):
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
    all_rows = parse(html)
    print(f"\n  ✓  {len(all_rows)} players parsed")
    advantage_str, top_props, team_stats = analyze(all_rows)
    send_discord(advantage_str, top_props, team_stats, DISCORD_WEBHOOK_2, 2, at)

def parse(html):    
    tables = pd.read_html(io.StringIO(html))   
    print(f"{tables[0]}\n\n")
    team_names = [re.sub(r'[A-Z]{2,}$', '', str(tables[0].iloc[0, 0])).strip(),
                  re.sub(r'[A-Z]{2,}$', '', str(tables[0].iloc[1, 0])).strip()]

    all_rows = []
    name_tables = [t for t in tables if t.shape[1] == 1]
    stat_tables  = [t for t in tables if t.shape[1] == 13]

    for idx, (nt, st) in enumerate(zip(name_tables, stat_tables)):
        team = team_names[idx] if idx < len(team_names) else f"Team {idx+1}"
        name_rows = [str(v) for v in nt.iloc[:, 0] if str(v).lower() not in JUNK and str(v) != "nan"]
        stat_rows = st[pd.to_numeric(st.iloc[:, 0], errors="coerce").notna()].values.tolist()
        for name, values in zip(name_rows, stat_rows):
            print(f"{name}")
            name = re.sub(r'[A-Z]\.\s.*', '', name).strip()
            record = {"player": name, "team": team, **dict(zip(STAT_HEADERS, values))}
            all_rows.append(record)
            print(f"  {team} {name[:22]:<22}  MIN={record['MIN']:>3}  PTS={record['PTS']:>3}  FG={record['FG']:>5}  TO={record['TO']:>2}\n")

    return all_rows