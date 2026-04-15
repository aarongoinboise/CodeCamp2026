import asyncio
import argparse
import csv
import schedule
import time
import requests
from bs4 import BeautifulSoup
from ollama import Client

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

ollama = Client()
MODEL = "llama3.1"


# ─────────────────────────────────────────────────────────────
# SCRAPING
# ─────────────────────────────────────────────────────────────

def fetch_html(url: str) -> str:
    headers = {
        "User-Agent": "Mozilla/5.0"
    }
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
    res = ollama.generate(
        model=MODEL,
        prompt=prompt
    )
    return res["response"]


# ─────────────────────────────────────────────────────────────
# OUTPUT
# ─────────────────────────────────────────────────────────────

def save_csv(site_key: str, data: str):
    filename = f"stats_{site_key}.csv"
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["raw_output"])
        writer.writerow([data])


def save_html(results: dict):
    html = """
    <html>
    <head><title>Dashboard</title></head>
    <body>
    <h1>Scraper Dashboard</h1>
    """

    for k, v in results.items():
        html += f"<h2>{k}</h2><pre>{v}</pre>"

    html += "</body></html>"

    with open("dashboard.html", "w", encoding="utf-8") as f:
        f.write(html)


# ─────────────────────────────────────────────────────────────
# JOB
# ─────────────────────────────────────────────────────────────

async def run_job(selected_sites):
    results = {}

    for key in selected_sites:
        site = SITES[key]
        print(f"\nScraping {site['name']}")

        html = fetch_html(site["url"])
        text = clean_html(html)

        result = extract_with_ai(text)

        results[key] = result

        save_csv(key, result)

    save_html(results)

    print("\nDONE")