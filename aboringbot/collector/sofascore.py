"""SofaScore: rounds, lineups (starters, goals, goalAssist, date of birth) and incidents
(substitution and red-card minutes).

Independent of Transfermarkt (own data operators). JSON is fetched through headless Chrome.

Minutes: SofaScore's own `minutesPlayed` counts added time. To compare like with like, minutes
are recomputed from the SofaScore lineup + incidents with the same convention as Transfermarkt
(nominal minute, match = 90', sub coming on in added time = 1'). The raw value is kept as
`minutes_raw` for the audit.
"""
import json
from datetime import datetime, timezone

API = "https://www.sofascore.com/api/v1"


def nominal_minutes(started, t_in, t_out):
    start = 0 if started else min(t_in, 90)
    end = 90 if t_out is None else min(t_out, 90)
    m = max(0, end - start)
    return 1 if (not started and m == 0) else m


def collect(fetcher, cfg, max_round, log=print):
    c = cfg["competition"]
    ut = c["sofascore_unique_tournament"]
    seasons = json.loads(fetcher.get(f"{API}/unique-tournament/{ut}/seasons"))["seasons"]
    sid = next(s["id"] for s in seasons if s["year"] == c["sofascore_season_year"])
    matches, apps, players, clubs, notes, no_lineup = [], [], {}, {}, [], []
    for rnd in range(1, max_round + 1):
        evs = json.loads(fetcher.get(f"{API}/unique-tournament/{ut}/season/{sid}/events/round/{rnd}"))["events"]
        for e in evs:
            if e.get("status", {}).get("type") != "finished":
                continue
            h, a = e["homeTeam"], e["awayTeam"]
            clubs[h["id"]], clubs[a["id"]] = h["name"], a["name"]
            m = dict(id=e["id"], round=rnd,
                     date=datetime.fromtimestamp(e["startTimestamp"], timezone.utc).strftime("%d/%m/%y"),
                     home=h["id"], away=a["id"], hg=e["homeScore"].get("current"), ag=e["awayScore"].get("current"),
                     url=f"https://www.sofascore.com/event/{e['id']}", lineups=True)
            matches.append(m)
            try:
                L = json.loads(fetcher.get(f"{API}/event/{e['id']}/lineups"))
            except RuntimeError:
                m["lineups"] = False; no_lineup.append(e["id"])
                notes.append(f"event {e['id']} R{rnd} {h['name']}-{a['name']}: no lineups published"); continue
            try:
                inc = json.loads(fetcher.get(f"{API}/event/{e['id']}/incidents"))["incidents"]
            except RuntimeError:
                inc = None; notes.append(f"event {e['id']}: no incidents, raw minutesPlayed used")
            t_in, t_out = {}, {}
            for x in inc or []:
                if x.get("incidentType") == "substitution":
                    if x.get("playerIn"): t_in[x["playerIn"]["id"]] = x["time"]
                    if x.get("playerOut"): t_out[x["playerOut"]["id"]] = x["time"]
                elif x.get("incidentType") == "card" and x.get("incidentClass") in ("red", "yellowRed") and x.get("player"):
                    t_out[x["player"]["id"]] = x["time"]
            for side, cid in (("home", h["id"]), ("away", a["id"])):
                for p in L.get(side, {}).get("players", []):
                    st = p.get("statistics") or {}
                    pl = p["player"]
                    dob = pl.get("dateOfBirthTimestamp")
                    dob = datetime.fromtimestamp(dob, timezone.utc).strftime("%Y-%m-%d") if dob is not None else None
                    players.setdefault(pl["id"], dict(name=pl["name"], dob=dob,
                                                      birth_year=int(dob[:4]) if dob else None,
                                                      position=pl.get("position"), club=cid,
                                                      url=f"https://www.sofascore.com/player/{pl.get('slug','x')}/{pl['id']}"))
                    started = not p.get("substitute")
                    raw = st.get("minutesPlayed")
                    if not started and pl["id"] not in t_in and not raw:
                        continue  # unused substitute
                    if inc is not None and (started or pl["id"] in t_in):
                        mins = nominal_minutes(started, t_in.get(pl["id"], 0), t_out.get(pl["id"]))
                    else:
                        mins = raw
                    apps.append(dict(match=e["id"], player=pl["id"], club=cid, started=started, minutes=mins,
                                     minutes_raw=raw, goals=st.get("goals", 0) or 0,
                                     assists=st.get("goalAssist", 0) or 0))
    log(f"[sofascore] {len(matches)} matches in rounds <= {max_round}, {len(apps)} appearances, "
        f"{len(no_lineup)} without lineups")
    return dict(source="sofascore", clubs=clubs, matches=matches, players=players, apps=apps, notes=notes,
                no_lineup=no_lineup, urls=dict(seasons=f"{API}/unique-tournament/{ut}/seasons"))
