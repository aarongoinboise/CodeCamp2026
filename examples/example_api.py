import requests

url = "https://cdn.espn.com/core/mens-college-basketball/boxscore?xhr=1&gameId=401856600"

headers = {
    "User-Agent": "Mozilla/5.0"
}

data = requests.get(url, headers=headers).json()

# teams
teams = data["gamepackageJSON"]["boxscore"]["teams"]

# players
players = data["gamepackageJSON"]["boxscore"]["players"]

for t in teams:
    name = t["team"]["displayName"]
    stats = {
    (s.get("abbreviation") or s.get("name")): s["displayValue"] for s in t["statistics"]
    }
    
    print(f"\n{name}")
    print(f"  FG: {stats.get('FG')} ({stats.get('FG%')}%)")
    print(f"  3PT: {stats.get('3PT')} ({stats.get('3P%')}%)")
    print(f"  FT: {stats.get('FT')} ({stats.get('FT%')}%)")
    print(f"  REB: {stats.get('REB')} | AST: {stats.get('AST')} | TO: {stats.get('TO')}")
    
print("\nPlayers:\n")
for team in players:
    team_name = team["team"]["displayName"]

    for group in team["statistics"]:
        for p in group["athletes"]:
            name = p["athlete"]["displayName"]

            stats = p.get("stats", [])

            if len(stats) < 6:
                continue

            mins, pts, fg, three, ft, reb = stats[:6]

            print(f"{name} ({team_name})")
            print(f"  PTS: {pts} | REB: {reb} | MIN: {mins}")
            print(f"  FG: {fg} | 3PT: {three} | FT: {ft}\n")