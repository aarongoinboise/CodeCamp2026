import os
import requests
from bs4 import BeautifulSoup
from ollama import Client
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()

# ─────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────

SITES = {
    "sports-ref": {
        "name": "Sports Reference",
        "url": "https://www.sports-reference.com/cbb/boxscores/2026-04-06-20-michigan.html",
    },
    "espn": {
        "name": "ESPN Box Score",
        "url": "https://www.espn.com/mens-college-basketball/boxscore/_/gameId/401856600",
    },
}
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")

ollama = Client()
MODEL = "llama3.1"


# ─────────────────────────────────────────────────────────────
# SCRAPING
# ─────────────────────────────────────────────────────────────

def fetch_html(url: str) -> str:
    headers = {"User-Agent": "Mozilla/5.0"}
    r = requests.get(url, headers=headers, timeout=30)
    r.raise_for_status()
    return r.text


def clean_html(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    return soup.get_text(separator="\n")


# ─────────────────────────────────────────────────────────────
# AI EXTRACTION
# ─────────────────────────────────────────────────────────────

def extract_with_ai(text: str) -> str:
    prompt = f"""
Extract structured basketball box score data.

Return JSON only.

TEXT:
{text[:20000]}
"""
    res = ollama.generate(model=MODEL, prompt=prompt)
    return res["response"]


# ─────────────────────────────────────────────────────────────
# DISCORD
# ─────────────────────────────────────────────────────────────

def send_discord(results: dict):
    now = datetime.now().strftime("%b %d %Y %I:%M %p")

    body  = f"**NCAA Championship — Game Update**\n"
    body += f"`{now}`\n"
    body += "=" * 40 + "\n\n"

    for key, result in results.items():
        site_name = SITES[key]["name"]
        body += f"**{site_name}**\n"
        body += "-" * 30 + "\n"
        body += f"{result}\n\n"

    requests.post(DISCORD_WEBHOOK, json={"content": body})
    print("  ✓  Discord message sent.")


# ─────────────────────────────────────────────────────────────
# JOB
# ─────────────────────────────────────────────────────────────

def run_job(selected_sites):
    results = {}

    for key in selected_sites:
        site = SITES[key]
        print(f"\nScraping {site['name']}")
        html   = fetch_html(site["url"])
        text   = clean_html(html)
        result = extract_with_ai(text)
        results[key] = result

    send_discord(results)
    print("\nDONE")

def run_espn():
    run_job(["espn"])