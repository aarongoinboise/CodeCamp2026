from datetime import datetime
import requests
import os
from dotenv import load_dotenv
load_dotenv()

GENERAL_WEBHOOK = os.getenv("GENERAL_WEBHOOK")

def send_discord(advantage_str, top_props, team_stats, discord_webhook, demo_num, at):
    now = datetime.now().strftime("%b %d %Y %I:%M %p")
    body = f"**DEMO {demo_num}: NCAA Championship — Michigan vs UConn**\n`{now}`\n"
    body += f"\n**ADVANTAGE:** {advantage_str}\n"
    body += "\n**TEAM TOTALS**\n"
    for team, stats in team_stats.items():
        body += f"{team}: TOV {stats['tov']}  FG% {stats['fg_pct']:.1%}\n"
    body += "\n**TOP PROPS**\n"
    for p in top_props:
        body += f"{p['player']} ({p['team']})  FG% {p['fg_pct']:.1%}  TOV {p['tov']}\n"
    webhook_url = GENERAL_WEBHOOK if at else discord_webhook
    requests.post(webhook_url, json={"content": body})
    print("  ✓  Discord message sent.")