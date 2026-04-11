"""
╔══════════════════════════════════════════════════════════╗
║  DEMO 2 — Getting Blocked → Getting Around It            ║
║  Part A: naive scraper hits ESPN/DraftKings, gets wall   ║
║  Part B: Playwright + evasion techniques bypass it       ║
╚══════════════════════════════════════════════════════════╝

WHY THIS MATTERS:
  Sportsbooks and ESPN update odds and live stats constantly.
  They also actively block bots — your fantasy football scraper
  probably died exactly this way. This demo shows the error live,
  then shows the fix.

INSTALL:
  pip install requests beautifulsoup4 playwright
  playwright install chromium

RUN PART A (gets blocked):
  python demo2_evasion.py --blocked

RUN PART B (works):
  python demo2_evasion.py --evade
"""

import sys
import time
import csv
import asyncio
import argparse
import random

# ── Part A: What a naive scraper looks like — and why it dies ───────────────

def naive_scrape_espn():
    """
    A plain requests call to ESPN's scoreboard.
    This is exactly what breaks: no browser fingerprint,
    no JS execution, no cookie handling.
    """
    import requests

    url = "https://www.espn.com/mens-college-basketball/scoreboard"

    print("\n  Sending request with default python-requests headers...")
    print(f"  URL: {url}\n")

    try:
        # No custom headers — this is what a bot looks like to the server
        response = requests.get(url, timeout=10)

        print(f"  Status code  : {response.status_code}")
        print(f"  Content-Type : {response.headers.get('content-type', '?')}")
        print(f"  Body length  : {len(response.text)} chars\n")

        if response.status_code == 403:
            print("  ⛔  403 FORBIDDEN — Server recognized us as a bot.")
            print("      This is what killed your fantasy football scraper.\n")
            return False

        if response.status_code == 429:
            print("  ⛔  429 TOO MANY REQUESTS — Rate limited.")
            print("      Try again later, or use delays/rotation (Demo 2B).\n")
            return False

        # Even a 200 might return a JS-only shell with no real data
        if "<script" in response.text and len(response.text) < 5000:
            print("  ⚠   Got 200 OK but the page is a JavaScript shell.")
            print("      There's no actual data here — just a blank React app.")
            print("      requests can't run JavaScript. That's the problem.\n")
            return False

        # Check if we got anti-bot interstitial (Cloudflare, etc.)
        if "cf-browser-verification" in response.text or "ray id" in response.text.lower():
            print("  ⛔  Cloudflare bot challenge detected.")
            print("      We'd need to solve a CAPTCHA to get through.\n")
            return False

        print("  We got a response — but check the content:")
        print("  " + response.text[:300] + "...\n")
        return True

    except Exception as e:
        print(f"  ⛔  Request failed: {e}\n")
        return False


def naive_scrape_covers():
    """
    Hits Covers.com for NCAAB odds — also likely to block plain requests.
    Covers is a common target for bettors pulling lines.
    """
    import requests

    url = "https://www.covers.com/sport/basketball/ncaab/odds"

    print("\n  Trying Covers.com odds page (a real bettor use case)...")
    print(f"  URL: {url}\n")

    try:
        response = requests.get(url, timeout=10)
        print(f"  Status: {response.status_code}")

        if response.status_code in [403, 429, 503]:
            print(f"  ⛔  Blocked with {response.status_code}.")
            return False

        from bs4 import BeautifulSoup
        soup = BeautifulSoup(response.text, "html.parser")

        # Look for actual odds data
        odds_rows = soup.select(".odds-table tr, [class*='odds'] tr, table tr")
        if not odds_rows:
            print("  ⚠   Page loaded but no odds data found.")
            print("      Odds are probably rendered by JavaScript after page load.")
            print("      requests only gets the empty HTML skeleton.\n")
            return False

        print(f"  Found {len(odds_rows)} rows — let's see if they have data...")
        return True

    except Exception as e:
        print(f"  ⛔  Error: {e}\n")
        return False


# ── Part B: Playwright — a real browser that acts like a human ───────────────

async def evade_and_scrape():
    """
    Uses Playwright to launch a real Chromium browser.
    We add stealth techniques so it doesn't look like automation:
      - Realistic User-Agent
      - Human-like mouse movement and delays
      - Proper viewport and locale settings
      - Disabling automation flags that sites check for
    """
    from playwright.async_api import async_playwright

    print("\n  Launching real Chromium browser (headless)...")
    print("  Adding stealth settings to hide automation fingerprint...\n")

    async with async_playwright() as p:
        # Launch browser with flags that reduce bot fingerprint
        browser = await p.chromium.launch(
            headless=True,   # set False to WATCH it work — great for a demo!
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",  # key flag
                "--disable-dev-shm-usage",
            ]
        )

        # Context = a browser session with realistic settings
        context = await browser.new_context(
            # Mimic a real MacBook Chrome user
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1440, "height": 900},
            locale="en-US",
            timezone_id="America/New_York",
            # Accept typical browser headers
            extra_http_headers={
                "Accept-Language": "en-US,en;q=0.9",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "DNT": "1",
            }
        )

        page = await context.new_page()

        # Inject JS to hide Playwright's automation markers
        # Sites check navigator.webdriver — we set it to false
        await page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => false });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });
            Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
        """)

        # ── Target: ESPN CBB Scoreboard ──────────────────────────────────────
        target = "https://www.espn.com/mens-college-basketball/scoreboard"
        print(f"  Navigating to: {target}")

        await page.goto(target, wait_until="networkidle", timeout=30000)

        # Human-like pause — we're "reading" the page
        delay = random.uniform(1.5, 3.0)
        print(f"  Waiting {delay:.1f}s (mimicking human reading time)...")
        await asyncio.sleep(delay)

        # Scroll like a human would
        await page.evaluate("window.scrollBy(0, 400)")
        await asyncio.sleep(random.uniform(0.5, 1.2))

        print(f"  Current URL  : {page.url}")
        print(f"  Page title   : {await page.title()}\n")

        # ── Extract live game data ────────────────────────────────────────────
        games = await extract_scoreboard(page)

        if games:
            print(f"  ✓  Found {len(games)} games on the scoreboard.")
            print_games(games)
            save_odds_csv(games, "live_games.csv")
        else:
            print("  ⚠  No games found — may be offseason or selectors changed.")
            print("     Try running with headless=False to watch the browser.")

        # ── Also try Covers.com for betting lines ─────────────────────────────
        print("\n  Now hitting Covers.com for NCAAB betting lines...")
        covers_lines = await scrape_covers_lines(page)

        if covers_lines:
            print(f"  ✓  Found {len(covers_lines)} lines.")
            save_odds_csv(covers_lines, "ncaab_lines.csv")

        await browser.close()
        print("\n  Browser closed cleanly.")


async def extract_scoreboard(page) -> list[dict]:
    """Pull game data from ESPN scoreboard using multiple selector strategies."""
    games = []

    # Strategy 1: Look for game score containers (ESPN's class names)
    # These change — that's OK, we have fallbacks
    selectors_to_try = [
        "section.Scoreboard",
        "[class*='ScoreboardPage']",
        "[class*='scoreboard']",
        "article[class*='game']",
    ]

    for selector in selectors_to_try:
        game_els = await page.query_selector_all(selector)
        if game_els:
            print(f"  Found {len(game_els)} game elements with '{selector}'")
            for el in game_els:
                try:
                    text = await el.inner_text()
                    # Simple parse — enough for a demo
                    lines = [l.strip() for l in text.split("\n") if l.strip()]
                    if len(lines) >= 2:
                        games.append({
                            "away_team": lines[0] if len(lines) > 0 else "",
                            "home_team": lines[1] if len(lines) > 1 else "",
                            "status": lines[2] if len(lines) > 2 else "Scheduled",
                            "raw": " | ".join(lines[:5]),
                        })
                except Exception:
                    continue
            if games:
                break

    # Strategy 2: Pull via ESPN's public JSON API (more reliable than scraping HTML)
    if not games:
        print("  HTML selectors didn't find games — trying ESPN's JSON API...")
        games = await fetch_espn_api(page)

    return games


async def fetch_espn_api(page) -> list[dict]:
    """
    ESPN exposes a public JSON API — much more reliable than parsing HTML.
    This is the right approach when a site has a hidden API.
    DevTools → Network tab → filter XHR → reload page → look for JSON responses.
    """
    api_url = (
        "https://site.api.espn.com/apis/site/v2/sports/basketball/"
        "mens-college-basketball/scoreboard"
    )
    print(f"  API endpoint: {api_url}")

    try:
        # Use Playwright to fetch the API (inherits our stealth context)
        response = await page.evaluate(f"""
            async () => {{
                const r = await fetch('{api_url}');
                return await r.json();
            }}
        """)

        games = []
        events = response.get("events", [])
        print(f"  API returned {len(events)} events.")

        for event in events:
            comp = event.get("competitions", [{}])[0]
            competitors = comp.get("competitors", [])

            home = next((c for c in competitors if c.get("homeAway") == "home"), {})
            away = next((c for c in competitors if c.get("homeAway") == "away"), {})
            status = event.get("status", {}).get("type", {}).get("description", "")
            odds_data = comp.get("odds", [{}])[0] if comp.get("odds") else {}

            games.append({
                "game_id": event.get("id", ""),
                "home_team": home.get("team", {}).get("displayName", ""),
                "away_team": away.get("team", {}).get("displayName", ""),
                "home_score": home.get("score", ""),
                "away_score": away.get("score", ""),
                "status": status,
                "spread": odds_data.get("details", ""),
                "over_under": odds_data.get("overUnder", ""),
                "home_win_pct": home.get("statistics", [{}])[0].get("value", "") if home.get("statistics") else "",
            })

        return games

    except Exception as e:
        print(f"  API call failed: {e}")
        return []


async def scrape_covers_lines(page) -> list[dict]:
    """Pull NCAAB lines from Covers.com."""
    try:
        await page.goto(
            "https://www.covers.com/sport/basketball/ncaab/odds",
            wait_until="domcontentloaded",
            timeout=20000
        )
        await asyncio.sleep(random.uniform(1.0, 2.0))

        # Extract via page text as a fallback
        rows = await page.query_selector_all("tr")
        lines = []
        for row in rows[:20]:
            text = await row.inner_text()
            cells = [c.strip() for c in text.split("\t") if c.strip()]
            if len(cells) >= 3:
                lines.append({"raw_line": " | ".join(cells[:5])})
        return lines

    except Exception as e:
        print(f"  Covers.com error: {e}")
        return []


# ── Helpers ──────────────────────────────────────────────────────────────────

def print_games(games: list[dict], n: int = 5):
    print()
    for g in games[:n]:
        home = g.get("home_team", "")[:20]
        away = g.get("away_team", "")[:20]
        status = g.get("status", "")[:15]
        spread = g.get("spread", "N/A")
        ou = g.get("over_under", "N/A")
        print(f"  {away:<22} @ {home:<22}  [{status:<12}]  spread: {spread}  O/U: {ou}")
    if len(games) > n:
        print(f"  ... and {len(games) - n} more games.")


def save_odds_csv(data: list[dict], filename: str):
    if not data:
        return
    keys = list(data[0].keys())
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(data)
    print(f"  ✓  Saved → '{filename}'")


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--blocked", action="store_true",
                        help="Run the naive scraper that gets blocked (Demo 2A)")
    parser.add_argument("--evade",   action="store_true",
                        help="Run the Playwright evader that works (Demo 2B)")
    args = parser.parse_args()

    if args.blocked:
        print("=" * 58)
        print("  DEMO 2A — Naive Scraper (This Gets Blocked)")
        print("=" * 58)
        print("\n  No custom headers. No browser. No JavaScript.")
        print("  This is exactly what your fantasy football scraper was.\n")

        ok1 = naive_scrape_espn()
        time.sleep(1)
        ok2 = naive_scrape_covers()

        if not ok1 and not ok2:
            print("\n  Both failed. Run with --evade to see the fix.")

    elif args.evade:
        print("=" * 58)
        print("  DEMO 2B — Playwright Evasion (This Works)")
        print("=" * 58)
        print("\n  Real browser + stealth flags + human-like behavior.")
        print("  Same sites, same data — bot protection bypassed.\n")
        asyncio.run(evade_and_scrape())

    else:
        print("Usage:")
        print("  python demo2_evasion.py --blocked   # show the failure first")
        print("  python demo2_evasion.py --evade     # show the fix")
        print()
        print("Tip for presentation: run --blocked first, let it fail,")
        print("then run --evade and show it pulling live game data.")
