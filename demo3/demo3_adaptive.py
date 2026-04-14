"""
╔══════════════════════════════════════════════════════════╗
║  DEMO 3 — The Adaptive Scraper (AI-Assisted)             ║
║  Uses Gemini to read raw HTML and extract structured     ║
║  data by INTENT — not by CSS selectors.                  ║
║                                                          ║
║  Two completely different sites. Two completely          ║
║  different HTML structures. One script. No selectors.    ║
╚══════════════════════════════════════════════════════════╝

WHY THIS MATTERS:
  Sports Reference and ESPN have totally different HTML layouts,
  class names, table structures, and data formats.

  A traditional scraper needs TWO separate parsers —
  one per site, maintained separately forever.

  This demo uses ONE AI extraction function that handles both.
  It understands CONTENT and INTENT, not CSS selectors.

  LIVE DEMO TRICK: Point at a third site mid-presentation.
  Zero code changes. Just a new URL.

INSTALL:
  pip install google-generativeai playwright
  playwright install chromium
  export GEMINI_API_KEY=your_key_here

  Get a free key at: https://aistudio.google.com

RUN:
  python demo3_adaptive.py                      # Run both sites (default)
  python demo3_adaptive.py --site sports-ref    # Sports Reference only
  python demo3_adaptive.py --site espn          # ESPN only
"""

import json
import os
import sys
import csv
import argparse
import asyncio
import google.generativeai as genai

# ── Target sites ───────────────────────────────────────────────────────────────

SITES = {
    "sports-ref": {
        "name": "Sports Reference (CBB)",
        "url": "https://www.sports-reference.com/cbb/boxscores/2026-04-06-20-michigan.html",
        "note": "Dense stats tables, Wikipedia-style HTML, minimal JS",
    },
    "espn": {
        "name": "ESPN Box Score",
        "url": "https://www.espn.com/mens-college-basketball/boxscore/_/gameId/401856600",
        "note": "React-rendered SPA, requires JS execution, ESPN proprietary classes",
    },
}

# ── AI Extraction ─────────────────────────────────────────────────────────────

def extract_with_ai(html: str, intent: str, source_label: str) -> dict:
    """
    Send raw HTML to Gemini and ask it to extract structured data.
    Works regardless of CSS class names, site structure, or JS framework.
    The same function handles Sports Reference AND ESPN without modification.
    """
    genai.configure(api_key=os.environ["GEMINI_API_KEY"])
    model = genai.GenerativeModel("gemini-2.0-flash")

    print(f"\n  Sending {source_label} HTML to Gemini ({len(html):,} chars)...")
    print(f"  Extraction intent: \"{intent[:80]}...\"\n")

    prompt = f"""You are a sports data extraction assistant. Extract structured box score data from this HTML.

SOURCE: {source_label}
EXTRACTION GOAL: {intent}

Return ONLY valid JSON. No explanation, no markdown, no code blocks — just raw JSON.

The JSON should have this structure:
{{
  "game": {{
    "home_team": "",
    "away_team": "",
    "home_score": 0,
    "away_score": 0,
    "game_date": "",
    "status": "",
    "spread": null,
    "over_under": null
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
      "ft": "",
      "steals": 0,
      "blocks": 0,
      "turnovers": 0
    }}
  ],
  "foul_trouble": [
    {{ "name": "", "team": "", "fouls": 0, "minutes": 0, "note": "" }}
  ],
  "injuries": [],
  "team_totals": []
}}

Rules:
- Include ALL players from BOTH teams with their team name filled in.
- For foul_trouble, include any player with 3+ fouls.
- If a field isn't present in the HTML, use null — never guess.
- minutes can be a decimal (e.g. 32.5) or integer, use whatever the source provides.
- Parse shooting as "made-attempted" strings (e.g. "7-12").

HTML (first 12000 chars):
{html[:12000]}"""

    response = model.generate_content(prompt)
    raw = response.text.strip()

    # Strip markdown fences if model added them despite instructions
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    try:
        data = json.loads(raw)
        player_count = len(data.get("players", []))
        print(f"  ✓  Gemini extracted {player_count} players from {source_label}.")
        return data
    except json.JSONDecodeError as e:
        print(f"  ⚠  JSON parse error from {source_label}: {e}")
        print(f"     Raw response snippet: {raw[:300]}")
        return {}


# ── Playwright scraper ─────────────────────────────────────────────────────────

async def scrape_and_extract(site_key: str) -> dict:
    """
    1. Use Playwright to fetch fully-rendered HTML (handles React/JS sites like ESPN)
    2. Pass raw HTML to Gemini for intent-based extraction
    No CSS selectors. No site-specific parsing logic. Just intent.
    """
    from playwright.async_api import async_playwright
    import asyncio as aio

    site = SITES[site_key]
    url  = site["url"]

    print(f"\n{'═' * 58}")
    print(f"  Site  : {site['name']}")
    print(f"  URL   : {url}")
    print(f"  Note  : {site['note']}")
    print(f"{'═' * 58}")
    print(f"\n  Launching headless browser...")

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

        # Suppress webdriver detection
        await page.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', { get: () => false });"
        )

        print(f"  Navigating to page...")
        await page.goto(url, wait_until="networkidle", timeout=45000)

        # ESPN is a React SPA — give it extra time to hydrate
        if site_key == "espn":
            print(f"  Waiting for ESPN React app to render...")
            await aio.sleep(4)
        else:
            await aio.sleep(1)

        html = await page.content()
        await browser.close()

    print(f"  Got {len(html):,} chars of rendered HTML.")

    intent = (
        "Extract the final game score, both teams' full player box score stats "
        "(points, rebounds, assists, steals, blocks, turnovers, fouls, FG, 3PT, FT, minutes), "
        "and flag any player with 3+ fouls as foul trouble — that's a live betting signal. "
        "Include both starters and bench players. Identify each player's team."
    )

    return extract_with_ai(html, intent, site["name"])


# ── Output helpers ─────────────────────────────────────────────────────────────

def print_results(data: dict, site_label: str):
    """Pretty-print extracted data with site label."""
    if not data:
        print(f"\n  [No data extracted from {site_label}]")
        return

    print(f"\n  ┌─ {site_label.upper()} ───────────────────────────────")

    game = data.get("game", {})
    if game:
        home  = game.get("home_team", "?")
        away  = game.get("away_team", "?")
        hs    = game.get("home_score", "?")
        as_   = game.get("away_score", "?")
        date  = game.get("game_date", "")
        status= game.get("status", "")
        print(f"  │  {away} @ {home}")
        print(f"  │  Score  : {as_} — {hs}")
        if date:   print(f"  │  Date   : {date}")
        if status: print(f"  │  Status : {status}")
        spread = game.get("spread")
        ou     = game.get("over_under")
        if spread: print(f"  │  Spread : {spread}   O/U: {ou}")
    print(f"  └────────────────────────────────────────────────")

    players = data.get("players", [])
    if players:
        print(f"\n  {'PLAYER':<22} {'TEAM':<12} {'POS':<5} {'MIN':<5} {'PTS':<5} "
              f"{'REB':<5} {'AST':<5} {'STL':<5} {'BLK':<5} {'TO':<5} {'FOULS':<7}")
        print("  " + "─" * 82)
        for p in players:
            foul_flag = " ⚠" if (p.get("fouls") or 0) >= 3 else ""
            team_abbr = str(p.get("team", ""))[:11]
            print(f"  {str(p.get('name','')):<22} "
                  f"{team_abbr:<12} "
                  f"{str(p.get('position','')):<5} "
                  f"{str(p.get('minutes','')):<5} "
                  f"{str(p.get('points','')):<5} "
                  f"{str(p.get('rebounds','')):<5} "
                  f"{str(p.get('assists','')):<5} "
                  f"{str(p.get('steals','')):<5} "
                  f"{str(p.get('blocks','')):<5} "
                  f"{str(p.get('turnovers','')):<5} "
                  f"{str(p.get('fouls','')):<7}"
                  f"{foul_flag}")

    foul_trouble = data.get("foul_trouble", [])
    if foul_trouble:
        print(f"\n  ⚠  FOUL TROUBLE ({len(foul_trouble)} player(s) with 3+ fouls):")
        for p in foul_trouble:
            print(f"     {p.get('name')} ({p.get('team','')}) — "
                  f"{p.get('fouls')} fouls in {p.get('minutes')} min  |  {p.get('note','')}")
        print()
        print("  → Live bet signal: high-foul players likely sit. Adjust spread model.")

    injuries = data.get("injuries", [])
    if injuries:
        print(f"\n  INJURY REPORT:")
        for inj in injuries:
            print(f"     {inj}")


def save_to_csv(data: dict, filename: str):
    """Save player stats to CSV for model input."""
    players = data.get("players", [])
    if not players:
        return

    game = data.get("game", {})
    for p in players:
        p["game_home"]   = game.get("home_team", "")
        p["game_away"]   = game.get("away_team", "")
        p["home_score"]  = game.get("home_score", "")
        p["away_score"]  = game.get("away_score", "")
        p["spread"]      = game.get("spread", "")
        p["over_under"]  = game.get("over_under", "")

    keys = list(players[0].keys())
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(players)

    print(f"\n  ✓  Saved → '{filename}' ({len(players)} rows)")
    print("     Ready to feed into your betting model or analysis script.")


# ── Entry point ───────────────────────────────────────────────────────────────

async def main():
    parser = argparse.ArgumentParser(
        description="AI-Assisted Adaptive Scraper — works across different sites without site-specific parsers."
    )
    parser.add_argument(
        "--site",
        choices=["sports-ref", "espn", "both"],
        default="both",
        help="Which site to scrape (default: both, to demonstrate cross-site resilience)"
    )
    args = parser.parse_args()

    print("=" * 58)
    print("  DEMO 3 — AI-Assisted Adaptive Scraper")
    print("  One extraction function. Two totally different sites.")
    print("=" * 58)

    if not os.environ.get("GEMINI_API_KEY"):
        print("\n  ⚠  GEMINI_API_KEY not set.")
        print("     Get a free key at: https://aistudio.google.com")
        print("     export GEMINI_API_KEY=your_key_here\n")
        sys.exit(1)

    sites_to_run = (
        ["sports-ref", "espn"] if args.site == "both"
        else [args.site]
    )

    all_results = {}

    for site_key in sites_to_run:
        try:
            data = await scrape_and_extract(site_key)
            all_results[site_key] = data
            print_results(data, SITES[site_key]["name"])
            if data:
                csv_file = f"stats_{site_key.replace('-', '_')}.csv"
                save_to_csv(data, csv_file)
        except Exception as e:
            print(f"\n  ✗  Failed to scrape {SITES[site_key]['name']}: {e}")
            all_results[site_key] = {}

    # ── The punchline ──────────────────────────────────────────────────────────
    print("\n" + "=" * 58)
    print("  THE KEY INSIGHT")
    print("=" * 58)
    print("""
  Sports Reference:  Dense Wikipedia-style tables, static HTML,
                     class names like 'right', 'center', 'thead'.

  ESPN:              React SPA, JavaScript-rendered DOM, proprietary
                     class hashes like 'ScoreCell__Score--xxxx'.

  Traditional approach: Two separate scrapers. Constant maintenance.
                         Break every time either site updates.

  This approach: ONE extract_with_ai() function.
                 Describe WHAT you want. Not WHERE it is.
                 Same function works on any site you point it at.

  → To add a third site: just pass a new URL. Zero code changes.
""")


if __name__ == "__main__":
    asyncio.run(main())