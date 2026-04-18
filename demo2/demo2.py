"""
DEMO 2 — Getting Blocked → Getting Around It
Part A: naive requests call → 403
Part B: Playwright with stealth → hits ESPN API → sends Discord message with stats
"""

import asyncio
import random
import re
from datetime import datetime
import os
import requests
from playwright.async_api import async_playwright
from dotenv import load_dotenv
load_dotenv()

URL        = "https://www.espn.com/mens-college-basketball/boxscore/_/gameId/401856600"
API_URL    = "https://site.web.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/summary?event=401856600"
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
        print("      CloudFront fingerprinted us as a bot at the network edge:\n")
        print(dict(response.headers))
        print(response.text)
        print("\n      Run with --evade to see how Playwright gets through.\n")
        return

    print("\n  ⚠  200 OK but page is a blank React shell — no data without JS.\n")


# ── Part B: Playwright — grabs cookies, hits API ─────────────────────────────

async def evade_and_scrape():
    print(f"\n  URL: {URL}")
    print("  Launching Chromium to grab ESPN session cookies...\n")

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

        print("  Navigating to ESPN to seed cookies...")
        await page.goto(URL, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(random.uniform(1.5, 2.5))

        cookies = await context.cookies()
        await browser.close()

    print(f"  ✓  {len(cookies)} cookies captured\n")

    # Convert Playwright cookies to requests format
    session = requests.Session()
    for c in cookies:
        session.cookies.set(c["name"], c["value"], domain=c["domain"])

    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Referer": URL,
        "Accept": "application/json",
    })

    print(f"  Hitting ESPN API...")
    resp = session.get(API_URL, timeout=15)
    print(f"  Status: {resp.status_code}\n")
    resp.raise_for_status()
    data = resp.json()

    all_rows = []
    team_names = []

    for team_data in data["boxscore"]["players"]:
        team_name = team_data["team"]["displayName"]
        team_names.append(team_name)
        for group in team_data["statistics"]:
            labels  = group["labels"]   # ["MIN","PTS","FG","3PT","FT","REB","AST","TO","STL","BLK","OREB","DREB","PF"]
            is_bench = group.get("type", "") == "bench"
            for athlete in group["athletes"]:
                if not athlete.get("stats") or athlete["stats"][0] == "":
                    continue
                name  = athlete["athlete"]["displayName"]
                stats = athlete["stats"]
                record = {
                    "team":    team_name,
                    "player":  name,
                    "starter": "N" if is_bench else "Y",
                }
                for i, label in enumerate(labels):
                    record[label] = stats[i] if i < len(stats) else ""
                all_rows.append(record)
                print(f"  {team_name[:6]} {name[:22]:<22}  "
                      f"MIN={record.get('MIN','?'):>3}  PTS={record.get('PTS','?'):>3}  "
                      f"FG={record.get('FG','?'):>5}  TO={record.get('TO','?'):>2}")

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
        total_tov = sum(int(p.get("TO", 0) or 0) for p in players if p.get("TO","").isdigit())
        fg_parts  = [p.get("FG","0-0").split("-") for p in players if "-" in p.get("FG","")]
        total_fg  = sum(int(m) for m,a in fg_parts)
        total_fga = sum(int(a) for m,a in fg_parts)
        fg_pct = total_fg / total_fga if total_fga else 0
        team_stats[team] = {"tov": total_tov, "fg_pct": fg_pct}

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
        try:
            tov    = int(row.get("TO", 0) or 0)
            fg_str = row.get("FG", "0-0") or "0-0"
            made, att = fg_str.split("-")
            fg_pct = int(made) / int(att) if int(att) > 0 else 0
            player_scores.append({
                "player": row["player"],
                "team":   row["team"],
                "tov":    tov,
                "fg_pct": fg_pct,
                "score":  fg_pct - (tov * 0.05),
            })
        except:
            continue

    top_props = sorted(player_scores, key=lambda x: x["score"], reverse=True)[:3]
    return advantage_str, top_props, team_stats


# ── Send Discord ──────────────────────────────────────────────────────────────

def send_discord(advantage_str, top_props, team_stats):
    now = datetime.now().strftime("%b %d %Y %I:%M %p")

    body  = f"**NCAA Championship — Michigan vs UConn**\n`{now}`\n"
    body += f"\n**ADVANTAGE:** {advantage_str}\n"
    body += "\n**TEAM TOTALS**\n"
    for team, stats in team_stats.items():
        body += f"{team}: TOV {stats['tov']}  FG% {stats['fg_pct']:.1%}\n"
    body += "\n**TOP PROPS**\n"
    for p in top_props:
        body += f"{p['player']} ({p['team']})  FG% {p['fg_pct']:.1%}  TOV {p['tov']}\n"

    requests.post(DISCORD_WEBHOOK, json={"content": body})
    print("  ✓  Discord message sent.")