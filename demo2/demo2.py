"""
DEMO 2 — Getting Blocked → Getting Around It
Part A: naive requests call → 403
Part B: Playwright with stealth → box score CSV + HTML
"""

import csv
import asyncio
import random
from datetime import datetime
import requests
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
import subprocess

URL = "https://www.espn.com/mens-college-basketball/boxscore/_/gameId/401856600"
CSV_FILE  = "boxscore.csv"
HTML_FILE = "boxscore.html"

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

        # Table 0 = score summary
        # Table 1 = UConn player names
        # Table 2 = UConn stats
        # Table 3 = Michigan player names
        # Table 4 = Michigan stats
        # Table 5 = Big East standings
        # Table 6 = Big Ten standings
        stat_headers = ["MIN", "PTS", "FG", "3PT", "FT", "REB", "AST", "TO", "STL", "BLK", "OREB", "DREB", "PF"]
        teams = [
            ("UConn Huskies",       tables[1], tables[2]),
            ("Michigan Wolverines", tables[3], tables[4]),
        ]

        all_rows = []
        for team_name, name_table, stat_table in teams:
            is_starter = True

            # Clean stat rows — strip header rows, totals, and shooting pct rows
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
        headers = ["team", "player", "starter"] + stat_headers
        save_csv(all_rows, headers, CSV_FILE)
        save_html(all_rows, headers, HTML_FILE)


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

    # Top 3 props: best FG% with fewest turnovers
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


# ── Output helpers ────────────────────────────────────────────────────────────

def save_csv(rows, headers, filename):
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    print(f"  ✓  CSV  saved → '{filename}'")


def save_html(rows, headers, filename):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    th_cells = "".join(f"<th>{h}</th>" for h in headers)

    advantage_str, top_props, team_stats = analyze(rows)
    team_stats_rows = ""
    for team, stats in team_stats.items():
        team_stats_rows += (
            f"<tr><td>{team}</td><td>{stats['tov']}</td><td>{stats['fg_pct']:.1%}</td></tr>\n"
        )

    props_rows = ""
    for p in top_props:
        props_rows += (
            f"<tr><td>{p['player']}</td><td>{p['team']}</td>"
            f"<td>{p['fg_pct']:.1%}</td><td>{p['tov']}</td></tr>\n"
        )

    teams = {}
    for row in rows:
        teams.setdefault(row["team"], []).append(row)

    body = ""
    for team, players in teams.items():
        starters = [p for p in players if p["starter"] == "Y"]
        bench    = [p for p in players if p["starter"] == "N"]

        body += f'<tr class="team-header"><td colspan="{len(headers)}">{team}</td></tr>\n'
        body += f'<tr class="group-header"><td colspan="{len(headers)}">Starters</td></tr>\n'
        for row in starters:
            tds = "".join(f"<td>{row.get(h, '')}</td>" for h in headers)
            body += f"<tr>{tds}</tr>\n"
        body += f'<tr class="group-header"><td colspan="{len(headers)}">Bench</td></tr>\n'
        for row in bench:
            tds = "".join(f"<td>{row.get(h, '')}</td>" for h in headers)
            body += f"<tr>{tds}</tr>\n"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>2026 NCAA Championship Box Score</title>
<style>
  body {{ font-family: Arial, sans-serif; font-size: 13px; padding: 16px; background: #fff; color: #000; }}
  h2   {{ margin: 0 0 4px 0; }}
  h3   {{ margin: 16px 0 6px 0; font-size: 14px; }}
  p    {{ margin: 0 0 12px 0; color: #555; font-size: 11px; }}
  table {{ border-collapse: collapse; width: 100%; margin-bottom: 24px; }}
  th, td {{ border: 1px solid #ccc; padding: 5px 8px; text-align: left; white-space: nowrap; }}
  th {{ background: #f0f0f0; font-weight: bold; }}
  tr:nth-child(even) {{ background: #f9f9f9; }}
  tr:hover {{ background: #fffbcc; }}
  tr.team-header td  {{ background: #002d62; color: #fff; font-weight: bold; font-size: 14px; padding: 8px; }}
  tr.group-header td {{ background: #dde3ec; font-weight: bold; font-size: 12px; }}
  .advantage {{ background: #e8f5e9; border: 1px solid #a5d6a7; padding: 10px 14px; border-radius: 4px; margin-bottom: 16px; font-size: 14px; }}
  .advantage strong {{ color: #1b5e20; }}
  .props {{ background: #fff8e1; border: 1px solid #ffe082; padding: 10px 14px; border-radius: 4px; margin-bottom: 24px; }}
  .props h3 {{ margin: 0 0 8px 0; color: #e65100; }}
</style>
</head>
<body>
<h2>2026 NCAA Championship — Michigan vs UConn</h2>
<p>Michigan 69 · UConn 63 &nbsp;|&nbsp; April 6, 2026 · Lucas Oil Stadium &nbsp;|&nbsp; Last updated: {now}</p>

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
  <h3>Possible Props — Best FG% &amp; Fewest Turnovers</h3>
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

    with open(filename, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  ✓  HTML saved → '{filename}'")

# ── Push to GitHub ────────────────────────────────────────────────────────────

def push_to_github():
    try:
        subprocess.run(["git", "add", "boxscore.html", "boxscore.csv"], check=True)
        subprocess.run(["git", "commit", "-m", f"refresh {datetime.now().strftime('%Y-%m-%d %H:%M')}"], check=True)
        subprocess.run(["git", "push"], check=True)
        print("Pushed to GitHub.")
    except subprocess.CalledProcessError as e:
        print(f"Git push failed: {e}")