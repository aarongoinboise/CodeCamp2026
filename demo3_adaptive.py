"""
╔══════════════════════════════════════════════════════════╗
║  DEMO 3 — The Adaptive Scraper (AI-Assisted)             ║
║  Uses Claude to read raw HTML and extract structured     ║
║  data by INTENT — not by CSS selectors.                  ║
║                                                          ║
║  When the site changes its class names overnight,        ║
║  this still works. CSS selectors break. AI doesn't.      ║
╚══════════════════════════════════════════════════════════╝

WHY THIS MATTERS:
  A sportsbook updates their UI. Your selectors break at 2am.
  Your model stops getting data. You lose your edge.

  This demo shows a scraper that uses an AI model to extract
  "the player stats table" by understanding the HTML —
  not by matching a class name that might change tomorrow.

  LIVE DEMO TRICK: Edit LOCAL_HTML mid-presentation to scramble
  the class names. Show it still extracts the right data.

INSTALL:
  pip install requests beautifulsoup4 anthropic playwright
  playwright install chromium
  export ANTHROPIC_API_KEY=your_key_here

RUN:
  python demo3_adaptive.py --local     # Use bundled HTML (no network needed)
  python demo3_adaptive.py --live      # Scrape a real site, then parse with AI
"""

import json
import os
import sys
import csv
import argparse
import asyncio
import anthropic

# ── Bundled sample HTML ───────────────────────────────────────────────────────
# This simulates a sportsbook / stats page.
# DEMO TRICK: During presentation, change class names like 'player-name' to
# 'pname-v2' or 'athlete-label' — the AI still extracts correctly.
# A CSS-selector scraper would completely break.

LOCAL_HTML = """
<!DOCTYPE html>
<html>
<head><title>NCAAB Live Player Stats — Kansas vs Duke</title></head>
<body>
  <div class="game-header">
    <span class="team-name">Kansas Jayhawks</span>
    <span class="score-display">72</span>
    <span class="vs-separator">vs</span>
    <span class="team-name">Duke Blue Devils</span>
    <span class="score-display">68</span>
    <span class="game-clock">2nd Half — 4:32</span>
  </div>

  <div class="betting-line">
    <span class="spread-label">Spread:</span>
    <span class="spread-value">Kansas -3.5</span>
    <span class="ou-label">O/U:</span>
    <span class="ou-value">145.5</span>
    <span class="last-updated">Updated: 4:31:08 PM ET</span>
  </div>

  <table class="player-stats-table" id="kansas-box-score">
    <caption>Kansas — Live Box Score</caption>
    <thead>
      <tr>
        <th class="col-name">Player</th>
        <th class="col-pos">POS</th>
        <th class="col-min">MIN</th>
        <th class="col-pts">PTS</th>
        <th class="col-reb">REB</th>
        <th class="col-ast">AST</th>
        <th class="col-fouls">FOULS</th>
        <th class="col-plus-minus">+/-</th>
        <th class="col-fg">FG</th>
        <th class="col-fg3">3PT</th>
        <th class="col-ft">FT</th>
      </tr>
    </thead>
    <tbody>
      <tr class="player-row">
        <td class="player-name">Hunter Dickinson</td>
        <td class="player-pos">C</td>
        <td class="player-min">26</td>
        <td class="player-pts">18</td>
        <td class="player-reb">9</td>
        <td class="player-ast">2</td>
        <td class="player-fouls">3</td>
        <td class="player-pm">+8</td>
        <td class="player-fg">7-12</td>
        <td class="player-fg3">0-0</td>
        <td class="player-ft">4-5</td>
      </tr>
      <tr class="player-row">
        <td class="player-name">Kevin McCullar Jr.</td>
        <td class="player-pos">G</td>
        <td class="player-min">28</td>
        <td class="player-pts">14</td>
        <td class="player-reb">4</td>
        <td class="player-ast">5</td>
        <td class="player-fouls">1</td>
        <td class="player-pm">+6</td>
        <td class="player-fg">5-10</td>
        <td class="player-fg3">2-4</td>
        <td class="player-ft">2-2</td>
      </tr>
      <tr class="player-row">
        <td class="player-name">Dajuan Harris Jr.</td>
        <td class="player-pos">G</td>
        <td class="player-min">24</td>
        <td class="player-pts">8</td>
        <td class="player-reb">2</td>
        <td class="player-ast">7</td>
        <td class="player-fouls">2</td>
        <td class="player-pm">+4</td>
        <td class="player-fg">3-6</td>
        <td class="player-fg3">1-2</td>
        <td class="player-ft">1-2</td>
      </tr>
      <tr class="player-row">
        <td class="player-name">KJ Adams Jr.</td>
        <td class="player-pos">F</td>
        <td class="player-min">22</td>
        <td class="player-pts">10</td>
        <td class="player-reb">6</td>
        <td class="player-ast">1</td>
        <td class="player-fouls">4</td>
        <td class="player-pm">-2</td>
        <td class="player-fg">4-7</td>
        <td class="player-fg3">0-1</td>
        <td class="player-ft">2-3</td>
      </tr>
      <tr class="player-row">
        <td class="player-name">Nicolas Timberlake</td>
        <td class="player-pos">G</td>
        <td class="player-min">20</td>
        <td class="player-pts">11</td>
        <td class="player-reb">3</td>
        <td class="player-ast">2</td>
        <td class="player-fouls">2</td>
        <td class="player-pm">+5</td>
        <td class="player-fg">4-8</td>
        <td class="player-fg3">2-5</td>
        <td class="player-ft">1-1</td>
      </tr>
      <tr class="player-row bench-player">
        <td class="player-name">Elmarko Jackson</td>
        <td class="player-pos">G</td>
        <td class="player-min">8</td>
        <td class="player-pts">4</td>
        <td class="player-reb">1</td>
        <td class="player-ast">1</td>
        <td class="player-fouls">1</td>
        <td class="player-pm">0</td>
        <td class="player-fg">2-3</td>
        <td class="player-fg3">0-1</td>
        <td class="player-ft">0-0</td>
      </tr>
    </tbody>
  </table>

  <div class="injury-report">
    <h3>Injury Report</h3>
    <ul>
      <li class="injury-item"><span class="inj-player">Gradey Dick</span> — <span class="inj-team">Kansas</span> — <span class="inj-status">Questionable (ankle)</span></li>
    </ul>
  </div>
</body>
</html>
"""

# ── AI Extraction ─────────────────────────────────────────────────────────────

def extract_with_ai(html: str, intent: str) -> dict:
    """
    Send raw HTML to Claude and ask it to extract structured data.
    Works even if class names change — it understands CONTENT, not selectors.
    """
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

    print(f"\n  Sending HTML to Claude ({len(html)} chars)...")
    print(f"  Extraction intent: \"{intent}\"\n")

    prompt = f"""You are a data extraction assistant. Extract structured sports data from this HTML.

EXTRACTION GOAL: {intent}

Return ONLY valid JSON. No explanation, no markdown, no code blocks — just raw JSON.

The JSON should have this structure:
{{
  "game": {{
    "home_team": "",
    "away_team": "",
    "home_score": 0,
    "away_score": 0,
    "clock": "",
    "spread": "",
    "over_under": ""
  }},
  "players": [
    {{
      "name": "",
      "team": "",
      "position": "",
      "minutes": 0,
      "points": 0,
      "rebounds": 0,
      "assists": 0,
      "fouls": 0,
      "plus_minus": "",
      "fg": "",
      "fg3": "",
      "ft": ""
    }}
  ],
  "foul_trouble": [
    {{ "name": "", "fouls": 0, "minutes": 0, "note": "" }}
  ],
  "injuries": []
}}

Fill in every field you can find. For foul_trouble, include any player with 3+ fouls.
Set missing fields to null, never guess.

HTML:
{html[:8000]}"""

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}]
    )

    raw = message.content[0].text.strip()

    # Clean up if model wrapped in backticks despite instructions
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    try:
        data = json.loads(raw)
        print("  ✓  Claude extracted structured data successfully.")
        return data
    except json.JSONDecodeError as e:
        print(f"  ⚠  JSON parse error: {e}")
        print(f"     Raw response: {raw[:200]}")
        return {}


# ── Live scrape + AI extract ───────────────────────────────────────────────────

async def live_scrape_then_ai(url: str, intent: str) -> dict:
    """
    1. Use Playwright to get the fully-rendered HTML (handles JS sites)
    2. Pass it to Claude for extraction
    No CSS selectors. No brittle parsing. Just intent.
    """
    from playwright.async_api import async_playwright

    print(f"  Fetching live HTML from: {url}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1440, "height": 900},
        )
        page = await context.new_page()

        await page.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', { get: () => false });"
        )

        await page.goto(url, wait_until="networkidle", timeout=30000)
        import asyncio as aio
        await aio.sleep(2)

        html = await page.content()
        print(f"  Got {len(html):,} chars of rendered HTML.")
        await browser.close()

    return extract_with_ai(html, intent)


# ── Output helpers ─────────────────────────────────────────────────────────────

def print_results(data: dict):
    """Pretty-print the extracted structured data."""
    if not data:
        print("  No data to display.")
        return

    game = data.get("game", {})
    if game:
        print(f"\n  ┌─ GAME ─────────────────────────────────────────")
        print(f"  │  {game.get('away_team', '?')} @ {game.get('home_team', '?')}")
        print(f"  │  Score : {game.get('away_score', '?')} — {game.get('home_score', '?')}")
        print(f"  │  Clock : {game.get('clock', '?')}")
        print(f"  │  Spread: {game.get('spread', 'N/A')}   O/U: {game.get('over_under', 'N/A')}")
        print(f"  └────────────────────────────────────────────────")

    players = data.get("players", [])
    if players:
        print(f"\n  {'PLAYER':<22} {'POS':<5} {'MIN':<5} {'PTS':<5} {'REB':<5} {'AST':<5} {'FOULS':<7} {'+/-':<6}")
        print("  " + "─" * 62)
        for p in players:
            foul_flag = " ⚠" if (p.get("fouls") or 0) >= 3 else ""
            print(f"  {str(p.get('name','')):<22} "
                  f"{str(p.get('position','')):<5} "
                  f"{str(p.get('minutes','')):<5} "
                  f"{str(p.get('points','')):<5} "
                  f"{str(p.get('rebounds','')):<5} "
                  f"{str(p.get('assists','')):<5} "
                  f"{str(p.get('fouls','')):<7}"
                  f"{str(p.get('plus_minus','')):<6}"
                  f"{foul_flag}")

    foul_trouble = data.get("foul_trouble", [])
    if foul_trouble:
        print(f"\n  ⚠  FOUL TROUBLE ALERT (3+ fouls):")
        for p in foul_trouble:
            print(f"     {p.get('name')} — {p.get('fouls')} fouls in {p.get('minutes')} min  |  {p.get('note','')}")
        print()
        print("  → Live bet signal: high-foul players likely sit. Adjust spread model.")

    injuries = data.get("injuries", [])
    if injuries:
        print(f"\n  INJURY REPORT:")
        for inj in injuries:
            print(f"     {inj}")


def save_to_csv(data: dict, filename: str = "live_stats.csv"):
    """Save player stats to CSV for model input."""
    players = data.get("players", [])
    if not players:
        return

    game = data.get("game", {})
    for p in players:
        p["game_home"] = game.get("home_team", "")
        p["game_away"] = game.get("away_team", "")
        p["spread"]    = game.get("spread", "")
        p["over_under"]= game.get("over_under", "")

    keys = list(players[0].keys())
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(players)

    print(f"\n  ✓  Player stats saved → '{filename}'")
    print("     Ready to feed into your betting model or analysis script.")


# ── Demo trick: scramble the HTML to prove AI still works ─────────────────────

def scramble_html(html: str) -> str:
    """
    Simulate a site redesign by renaming all class attributes.
    This breaks every CSS-selector scraper.
    The AI-based scraper still works because it reads content, not classes.
    """
    import re

    redesigned = html.replace('class="player-name"',    'class="athlete-display-v3"')
    redesigned = redesigned.replace('class="player-pts"',  'class="stat-col-points-2024"')
    redesigned = redesigned.replace('class="player-fouls"','class="violation-count-live"')
    redesigned = redesigned.replace('class="player-row"',  'class="data-row-entry"')
    redesigned = redesigned.replace('class="team-name"',   'class="franchise-identifier"')
    redesigned = redesigned.replace('class="score-display"', 'class="score-v2-live-int"')
    redesigned = redesigned.replace('id="kansas-box-score"', 'id="box-xk82-live"')

    print("  ⚡  Site 'redesigned' — all class names changed.")
    print("     A CSS-selector scraper would return zero rows right now.")
    print("     Let's see if the AI can still read it...\n")
    return redesigned


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--local",    action="store_true", help="Use bundled sample HTML (no network)")
    parser.add_argument("--live",     action="store_true", help="Scrape a live ESPN page")
    parser.add_argument("--scramble", action="store_true", help="Scramble class names first (demo the resilience)")
    args = parser.parse_args()

    print("=" * 58)
    print("  DEMO 3 — AI-Assisted Adaptive Scraper")
    print("=" * 58)

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("\n  ⚠  ANTHROPIC_API_KEY not set.")
        print("     export ANTHROPIC_API_KEY=your_key_here\n")
        sys.exit(1)

    intent = (
        "Extract the live game score, spread, over/under, "
        "all player box score stats, and flag any player with 3+ fouls "
        "as foul trouble — those are live betting signals."
    )

    if args.local or not args.live:
        print("\n  Using bundled sample HTML (works offline, great for demos).")

        html = LOCAL_HTML

        if args.scramble:
            print()
            html = scramble_html(html)

        data = extract_with_ai(html, intent)

    else:
        print("\n  Scraping live ESPN CBB scoreboard...")
        url = "https://www.espn.com/mens-college-basketball/scoreboard"
        data = asyncio.run(live_scrape_then_ai(url, intent))

    print_results(data)

    if data:
        save_to_csv(data)

    print("\n  The key insight:")
    print("  → CSS selectors break when sites change. Intent-based AI extraction doesn't.")
    print("  → You described WHAT you want, not WHERE it is in the HTML.")
    print("  → Same script works tomorrow even if the sportsbook redesigns overnight.\n")
