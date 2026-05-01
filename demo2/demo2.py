"""
DEMO 2 — Getting Blocked → Getting Around It
Part A: naive requests call → 403
Part B: Playwright with stealth → scrapes the page directly → sends Discord message with stats
"""

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
load_dotenv()

URL = "https://www.espn.com/mens-college-basketball/boxscore/_/gameId/401856600"
DISCORD_WEBHOOK_2 = os.getenv("DISCORD_WEBHOOK")
GENERAL_WEBHOOK = os.getenv("GENERAL_WEBHOOK")
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
    tables = pd.read_html(io.StringIO(html))    
    team_names = [re.sub(r'[A-Z]{2,}$', '', str(tables[0].iloc[0, 0])).strip(),
                  re.sub(r'[A-Z]{2,}$', '', str(tables[0].iloc[1, 0])).strip()]

    all_rows = []
    JUNK = {"starters", "bench", "team"}
    name_tables = [t for t in tables if t.shape[1] == 1]
    stat_tables  = [t for t in tables if t.shape[1] == 13]

    for idx, (nt, st) in enumerate(zip(name_tables, stat_tables)):
        team = team_names[idx] if idx < len(team_names) else f"Team {idx+1}"
        name_rows = [str(v) for v in nt.iloc[:, 0] if str(v).lower() not in JUNK and str(v) != "nan"]
        stat_rows = st[pd.to_numeric(st.iloc[:, 0], errors="coerce").notna()].values.tolist()
        for name, values in zip(name_rows, stat_rows):
            name = re.sub(r'[A-Z]\.\s.*', '', name).strip()
            record = {"player": name, "team": team, **dict(zip(STAT_HEADERS, values))}
            all_rows.append(record)
            print(f"  {team} {name[:22]:<22}  MIN={record['MIN']:>3}  PTS={record['PTS']:>3}  FG={record['FG']:>5}  TO={record['TO']:>2}")

    print(f"\n  ✓  {len(all_rows)} players parsed")
    advantage_str, top_props, team_stats = analyze(all_rows)
    send_discord(advantage_str, top_props, team_stats, at)


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

def send_discord(advantage_str, top_props, team_stats, at):
    now = datetime.now().strftime("%b %d %Y %I:%M %p")
    body = f"**NCAA Championship — Michigan vs UConn**\n`{now}`\n"
    body += f"\n**ADVANTAGE:** {advantage_str}\n"
    body += "\n**TEAM TOTALS**\n"
    for team, stats in team_stats.items():
        body += f"{team}: TOV {stats['tov']}  FG% {stats['fg_pct']:.1%}\n"
    body += "\n**TOP PROPS**\n"
    for p in top_props:
        body += f"{p['player']} ({p['team']})  FG% {p['fg_pct']:.1%}  TOV {p['tov']}\n"
    webhook_url = GENERAL_WEBHOOK if at else DISCORD_WEBHOOK_2
    requests.post(webhook_url, json={"content": body})
    print("  ✓  Discord message sent.")