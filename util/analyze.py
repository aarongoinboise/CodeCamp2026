TOV_MULT = 0.05

def analyze(rows):
    team_stats = org_team_stats(rows)
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

def org_team_stats(rows):
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
    return teams