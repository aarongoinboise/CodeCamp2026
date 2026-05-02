TOV_MULT = 0.05

def analyze_sports_reference(rows):
    team_stats = org_team_stats_sports_reference(rows)
    advantage_team = min(team_stats, key=lambda t: (team_stats[t]["tov"], -team_stats[t]["fg_pct"]))
    adv = team_stats[advantage_team]
    advantage_str = f"{advantage_team} (TOV: {adv['tov']}, FG%: {adv['fg_pct']:.1%})"
    top_props = sorted(
        [{"player": p["player"], "team": p["team"],
          "tov": int(p["tov"]) if p.get("tov", "").isdigit() else 0,
          "fg_pct": int(p["fg"]) / int(p["fga"]) if p.get("fga", "0") not in ("0", "") else 0}
         for p in rows],
        key=lambda x: x["fg_pct"] - x["tov"] * TOV_MULT,
        reverse=True
    )[:3]
    return advantage_str, top_props, team_stats

def analyze_espn(rows):
    team_stats = org_team_stats_espn(rows)
    advantage_team = min(team_stats, key=lambda t: (team_stats[t]["tov"], -team_stats[t]["fg_pct"]))
    adv = team_stats[advantage_team]
    advantage_str = f"{advantage_team} (TOV: {adv['tov']}, FG%: {adv['fg_pct']:.1%})"

    top_props = sorted(
        [{"player": p["player"], "team": p["team"],
          "tov": int(p["TO"]) if p.get("TO", "").isdigit() else 0,
          "fg_pct": int(p["FG"].split("-")[0]) / int(p["FG"].split("-")[1])
                   if "-" in p.get("FG", "") and int(p["FG"].split("-")[1]) > 0 else 0}
         for p in rows],
        key=lambda x: x["fg_pct"] - x["tov"] * TOV_MULT,
        reverse=True
    )[:3]

    return advantage_str, top_props, team_stats

def analyze_general(data):
    players = data["players"]
    team_stats = org_team_stats_general(players)
    if len(players) < 2:
        return "Not enough data", [], team_stats
    advantage_team = min(team_stats, key=lambda t: (team_stats[t]["tov"], -team_stats[t]["fg_pct"]))
    adv = team_stats[advantage_team]
    advantage_str = f"{advantage_team} (TOV: {adv['tov']}, FG%: {adv['fg_pct']:.1%})"

    top_props = sorted(
        [{
            "player": p["name"],
            "team":   p["team"],
            "tov":    int(p["to"]) if p.get("to", "").isdigit() else 0,
            "fg_pct": int(p["fg"].split("-")[0]) / int(p["fg"].split("-")[1])
                      if "-" in p.get("fg", "") and int(p["fg"].split("-")[1]) > 0 else 0
        } for p in players],
        key=lambda x: x["fg_pct"] - x["tov"] * 0.05,
        reverse=True
    )[:3]
    return advantage_str, top_props, team_stats

def org_team_stats_sports_reference(rows):
    teams = {}
    for row in rows:
        teams.setdefault(row["team"], []).append(row)
    team_stats = {}
    for team, players in teams.items():
        total_tov = sum(int(p["tov"]) for p in players if p.get("tov", "").isdigit())
        total_fg = sum(int(p["fg"]) for p in players if p.get("fg", "").isdigit())
        total_fga = sum(int(p["fga"]) for p in players if p.get("fga", "").isdigit())
        team_stats[team] = {
            "tov": total_tov,
            "fg_pct": total_fg / total_fga if total_fga else 0
        }
    return team_stats

def org_team_stats_espn(rows):
    teams = {}
    for row in rows:
        teams.setdefault(row["team"], []).append(row)

    team_stats = {}
    for team, players in teams.items():
        total_tov = sum(int(p["TO"]) for p in players if p.get("TO", "").isdigit())
        fg_parts = [p["FG"].split("-") for p in players if "-" in p.get("FG", "")]
        total_fg = sum(int(m) for m, a in fg_parts)
        total_fga = sum(int(a) for m, a in fg_parts)
        team_stats[team] = {
            "tov": total_tov,
            "fg_pct": total_fg / total_fga if total_fga else 0
        }
    return team_stats

def org_team_stats_general(players):
    teams = {}
    for p in players:
        teams.setdefault(p["team"], []).append(p)

    team_stats = {}
    for team, roster in teams.items():
        fg_parts = [p["fg"].split("-") for p in roster if "-" in p.get("fg", "")]
        total_fg  = sum(int(m) for m, a in fg_parts)
        total_fga = sum(int(a) for m, a in fg_parts)
        team_stats[team] = {
            "tov":    sum(int(p["to"]) for p in roster if p.get("to", "").isdigit()),
            "fg_pct": total_fg / total_fga if total_fga else 0
        }
    return team_stats