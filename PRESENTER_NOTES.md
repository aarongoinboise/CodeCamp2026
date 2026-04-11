# The Unkillable Scraper — Presenter Quick Reference

## Setup (do this before the session)

```bash
pip install requests beautifulsoup4 playwright anthropic
playwright install chromium
export ANTHROPIC_API_KEY=your_key_here
```

---

## Session Flow

### Hook (0–5 min)
Show your actual fantasy football scraper error. If you don't have it handy,
pull up a 403 or bot-detection page in the browser to set the scene.
Talking point: *"This is why we're here."*

---

### Demo 1 — Basic Scraper (5–20 min)
**What it does:** Scrapes sports-reference.com for CBB player per-game stats.
Exports to CSV. No API key. No browser automation.

```bash
python demo1_basic_scraper.py
```

**Swap the team:** Edit `TEAM_SLUG` at the top. Options: `duke`, `kentucky`, `gonzaga`, `houston`, `uconn`

**Talking points:**
- This is your starting point for any stat-based model
- "You want foul-trouble history on Dickinson? Run this, open the CSV, done."
- Show the CSV in Excel or just cat it — audience loves seeing real data pop out
- This works because Sports Reference is relatively bot-tolerant *with a real UA header*

**What to show:** Terminal → CSV file open → point out the columns that matter for modeling

---

### Demo 2 — Getting Blocked → Getting Around It (20–35 min)

**Step 1: Show the failure**
```bash
python demo2_evasion.py --blocked
```
This hits ESPN with a plain requests call. It either 403s, or returns a JS shell
with no data. Either way — nothing useful comes back.

**Talking point:** *"This is exactly what your scraper looks like to a server.
No browser headers, no cookies, no JavaScript. It screams 'I'm a bot.'"*

**Step 2: Show the fix**
```bash
python demo2_evasion.py --evade
```
Same sites. Real Chromium browser, stealth flags, human-like delays.
If there are live games, you'll see scores and lines. Offseason = fewer results,
but the browser behavior and anti-detection is the main point.

**Bonus tip for the audience:** Open Chrome DevTools → Network → XHR tab → reload ESPN.
You'll see `scoreboard` in the API calls. That's the JSON endpoint we hit directly.
*"Sites have hidden APIs. Find them in DevTools. They're way more reliable than parsing HTML."*

**Key techniques shown:**
- `--disable-blink-features=AutomationControlled` — hides Playwright's fingerprint
- `navigator.webdriver = false` — what sites check first
- Random delays between actions — mimics human timing
- Realistic viewport, locale, timezone — part of the fingerprint

---

### Demo 3 — AI-Assisted Adaptive Scraper (35–50 min)

**Step 1: Run normally**
```bash
python demo3_adaptive.py --local
```
Pulls the bundled HTML, sends it to Claude, gets back structured JSON.
Show the foul-trouble alert — that's the live betting signal.

**Step 2: The live demo trick (this lands well)**
While it's running, open `demo3_adaptive.py` and change a class name in `LOCAL_HTML`.
Or just run with `--scramble`:
```bash
python demo3_adaptive.py --local --scramble
```
This renames every class attribute in the HTML — simulating a site redesign.
A CSS-selector scraper returns zero rows. The AI still extracts everything correctly.

**Talking point:** *"I described WHAT I want, not WHERE it is.
'Find the player stats and flag anyone with 3+ fouls.'
That works tomorrow even if DraftKings redesigns their UI tonight."*

**Step 3: Run against a live page (if you have API key and network)**
```bash
python demo3_adaptive.py --live
```

**Key concept to land:**
- Layer 1: requests + BeautifulSoup → fast, fragile, breaks on JS and bot walls
- Layer 2: Playwright → solves JS + bot detection, still breaks on site redesigns
- Layer 3: AI extraction → survives redesigns, understands intent, not structure

---

### Wrap-Up (50–60 min)

**One-slide decision tree:**
```
Need data from a sports site?
        │
        ▼
Does requests get it? ──YES──► Use Demo 1 (fast, simple)
        │
        NO
        ▼
Is it JS-rendered or bot-blocked? ──YES──► Add Playwright (Demo 2)
        │
        NO / Site keeps changing
        ▼
Use AI extraction (Demo 3) — describe what you want, not where it is
```

**Takeaways to say out loud:**
1. Start simple. Add complexity only when you hit a wall.
2. When you get blocked, check DevTools for a hidden JSON API first — it's easier than evading.
3. If you're tired of fixing broken selectors, let AI read the HTML instead.
4. The foul-trouble pattern is real: 3+ fouls in first half = adjusted rotation = live line movement.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| Sports Reference returns 429 | Add `time.sleep(3)` between requests, or run during off-peak hours |
| Playwright can't find Chromium | Run `playwright install chromium` |
| ESPN returns empty JS shell | The `--evade` script handles this — use `asyncio.run()` path |
| Claude API key not set | `export ANTHROPIC_API_KEY=sk-ant-...` |
| Demo 3 JSON parse error | Claude returned markdown — the script strips it, but check your key is valid |

---

## Files

| File | Demo | Purpose |
|---|---|---|
| `demo1_basic_scraper.py` | Layer 1 | requests + BS4, exports player stats CSV |
| `demo2_evasion.py` | Layer 2 | Shows blocked state then Playwright fix |
| `demo3_adaptive.py` | Layer 3 | AI-based extraction, survives site redesigns |
| `PRESENTER_NOTES.md` | This file | Run order and talking points |
