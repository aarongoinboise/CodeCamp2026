"""
DEMO 2 — Getting Blocked → Getting Around It
Part A: naive requests call → 403
Part B: Playwright with stealth → sends Discord message with stats
"""

import asyncio
import random
from datetime import datetime
import os
import requests
from bs4 import BeautifulSoup
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
        print("      CloudFront fingerprinted us as a bot at the network edge:\n")
        print(dict(response.headers))
        print(response.text)
        print("\n      Run with --evade to see how Playwright gets through.\n")
        return

    soup = BeautifulSoup(response.text, "html.parser")
    tables = soup.find_all("table")
    print(f"  Tables found : {len(tables)}")
    if not tables:
        print("\n  ⚠  200 OK but zero tables — page is a blank React shell.")
        print("     requests can't execute JavaScript. The data never loaded.\n")


# ── Part B: Playwright — real browser, real data ──────────────────────────────

async def evade_and_scrape():
    print(f"\n  URL: {URL}")
    print("  Launching Chromium with stealth settings...\n")

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

        print("  Navigating to box score page...")
        await page.goto(URL, wait_until="domcontentloaded", timeout=60000)

        try:
            await page.wait_for_selector(".Table__TBODY", timeout=15000)
            print("  ✓  Box score tables detected in DOM\n")
        except Exception:
            print("  ⚠  Timed out waiting for tables — trying anyway...\n")

        await asyncio.sleep(random.uniform(1.5, 2.5))

        tables = await page.evaluate("""
            () => {
                return Array.from(document.querySelectorAll('table')).map((t, i) => {
                    const headers = Array.from(t.querySelectorAll('th'))
                        .map(th => th.innerText.trim()).filter(Boolean);
                    const rows = Array.from(t.querySelectorAll('tr')).map(tr =>
                        Array.from(tr.querySelectorAll('td')).map(td => td.innerText.trim())
                    ).filter(r => r.length > 0);
                    return { index: i, headers, rows };
                });
            }
        """)

        await browser.close()
        print(f"  Browser closed. Found {len(tables)} tables.\n")

        stat_headers = ["MIN", "PTS", "FG", "3PT", "FT", "REB", "AST", "TO", "STL", "BLK", "OREB", "DREB", "PF"]
        teams = [
            ("UConn Huskies",       tables[1], tables[2]),
            ("Michigan Wolverines", tables[3], tables[4]),
        ]

        all_rows = []
        for team_name, name_table, stat_table in teams:
            is_starter = True

            clean_stats = []
            for row in stat_table['rows']:
                if not row:          continue
                if row[0] == 'MIN':  continue
                if row[0] == '':     continue
                if '%' in row[0]:    continue
                clean_stats.append(row)

            stat_idx = 0
            for name_row in name_table['rows']:
                cell = name_row[0].replace('\n', ' ').strip() if name_row else ''
                if not cell:           continue
                if cell == 'STARTERS': is_starter = True;  continue
                if cell == 'BENCH':    is_starter = False; continue
                if cell == 'TEAM':     continue

                stats = clean_stats[stat_idx] if stat_idx < len(clean_stats) else []
                stat_idx += 1

                record = {
                    "team":    team_name,
                    "player":  cell,
                    "starter": "Y" if is_starter else "N",
                }
                for i, col in enumerate(stat_headers):
                    record[col] = stats[i] if i < len(stats) else ""

                all_rows.append(record)
                print(f"  {team_name[:6]}  {record['starter']}  {cell[:22]:<22}  "
                      f"MIN={record['MIN']:>3}  PTS={record['PTS']:>3}  "
                      f"REB={record['REB']:>3}  PF={record['PF']:>3}")

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
        total_tov = 0
        total_fg  = 0
        total_fga = 0
        for p in players:
            try: total_tov += int(p.get("TO", 0) or 0)
            except: pass
            fg_str = p.get("FG", "0-0") or "0-0"
            try:
                made, att = fg_str.split("-")
                total_fg  += int(made)
                total_fga += int(att)
            except: pass
        fg_pct = total_fg / total_fga if total_fga else 0
        team_stats[team] = {"tov": total_tov, "fg_pct": fg_pct}

    sorted_tov   = sorted(team_stats, key=lambda t: team_stats[t]["tov"])
    sorted_fgpct = sorted(team_stats, key=lambda t: team_stats[t]["fg_pct"], reverse=True)

    scores = {t: 0 for t in team_stats}
    for rank, t in enumerate(sorted_tov):
        scores[t] += rank
    for rank, t in enumerate(sorted_fgpct):
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
            tov    = int(row.get("TO", 0) or 0)
            fg_str = row.get("FG", "0-0") or "0-0"
            made, att = fg_str.split("-")
            fg_pct = int(made) / int(att) if int(att) > 0 else 0
            score  = fg_pct - (tov * 0.05)
            player_scores.append({
                "player": name,
                "team":   row["team"],
                "tov":    tov,
                "fg_pct": fg_pct,
                "score":  score,
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