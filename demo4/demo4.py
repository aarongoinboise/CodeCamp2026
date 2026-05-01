import requests
from bs4 import BeautifulSoup
from datetime import datetime
import os
from dotenv import load_dotenv
load_dotenv()

ESPN_URL = "https://www.espn.com/mens-college-basketball/boxscore/_/gameId/401856600"
DISCORD_WEBHOOK_4 = os.getenv("DISCORD_WEBHOOK")
GENERAL_WEBHOOK = os.getenv("GENERAL_WEBHOOK")


# ── Raw Scraper ───────────────────────────────────────────────────────────────────

def fetch_raw(url):
    headers = {"User-Agent": "Mozilla/5.0"}
    resp = requests.get(url, headers=headers, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    return soup.get_text(separator="\n", strip=True)

def run(at=False):
    text = fetch_raw(ESPN_URL)
    now = datetime.now().strftime("%b %d %Y %I:%M %p")
    lines = [l for l in text.splitlines() if l.strip()][:150]
    body = f"DEMO 4 (raw fallback)\n\n**NCAA Championship Box Score**\n`{now}`\n\n```\n"
    body += "\n".join(lines)
    body += "\n```"
    body = body[:1900]
    webhook_url = GENERAL_WEBHOOK if at else DISCORD_WEBHOOK_4
    requests.post(webhook_url, json={"content": body})
    print("  ✓  Discord message sent.")

