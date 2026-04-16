import asyncio
import argparse
import schedule
import time
import smtplib
import os
import requests
from bs4 import BeautifulSoup
from ollama import Client
from email.mime.text import MIMEText
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
# EMAIL
# ─────────────────────────────────────────────────────────────

def send_email(results: dict):
    now = datetime.now().strftime("%b %d %Y %I:%M %p")

    body  = f"2026 NCAA Championship — Game Update\n"
    body += f"Last updated: {now}\n"
    body += "=" * 40 + "\n\n"

    for key, result in results.items():
        site_name = SITES[key]["name"]
        body += f"{site_name}\n"
        body += "-" * 30 + "\n"
        body += f"{result}\n\n"

    msg = MIMEText(body)
    msg["Subject"] = f"Game Update — {now}"
    msg["From"]    = os.environ.get("GMAIL_USER")
    msg["To"]      = os.environ.get("GMAIL_USER")

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(os.environ.get("GMAIL_USER"), os.environ.get("GMAIL_APP_PASSWORD"))
        server.send_message(msg)
    print("  ✓  Email sent.")


# ─────────────────────────────────────────────────────────────
# JOB
# ─────────────────────────────────────────────────────────────

async def run_job(selected_sites):
    results = {}

    for key in selected_sites:
        site = SITES[key]
        print(f"\nScraping {site['name']}")
        html   = fetch_html(site["url"])
        text   = clean_html(html)
        result = extract_with_ai(text)
        results[key] = result

    send_email(results)
    print("\nDONE")


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--sites", nargs="+", choices=list(SITES.keys()), default=list(SITES.keys()))
    parser.add_argument("--schedule", action="store_true")
    args = parser.parse_args()

    asyncio.run(run_job(args.sites))

    if args.schedule:
        schedule.every(5).minutes.do(lambda: asyncio.run(run_job(args.sites)))
        print("Running every 5 minutes. Press CTRL+C to stop.")
        while True:
            schedule.run_pending()
            time.sleep(1)