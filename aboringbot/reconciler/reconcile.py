"""Reconciler: TM x SofaScore -> reconciled CSV + audit log + identity log."""
import csv, json
from collections import defaultdict
from pathlib import Path

from .. import config as config_mod
from . import identity, rules, evidence as evidence_mod

FIELDS = ["presenze", "titolari", "minuti", "gol", "assist"]
KEY = {"minuti": "conf_minuti", "gol": "conf_gol", "assist": "conf_assist"}


def load(out):
    d = {}
    for s in ("tm", "sofascore"):
        p = Path(out) / f"source_{s}.json"
        if p.exists():
            x = json.loads(p.read_text())
            x["players"] = {str(k): v for k, v in x["players"].items()}
            x["clubs"] = {str(k): v for k, v in x["clubs"].items()}
            for m in x["matches"]:
                m["id"], m["home"], m["away"] = str(m["id"]), str(m["home"]), str(m["away"])
            for a in x["apps"]:
                a["match"], a["player"], a["club"] = str(a["match"]), str(a["player"]), str(a["club"])
                p_ = x["players"].get(a["player"])
                if p_ is not None and not p_.get("club"):
                    p_["club"] = a["club"]
            d[s] = x
    return d


def aggregate(src):
    """Per player totals over the collected matches (already cut at max round)."""
    tot = defaultdict(lambda: dict(presenze=0, titolari=0, minuti=0, gol=0, assist=0, club=None,
                                   minutes_unknown=0, per_match={}))
    order = {m["id"]: (m["round"], m["date"] or "") for m in src["matches"]}
    for a in sorted(src["apps"], key=lambda a: order.get(a["match"], (0, ""))):
        if a["match"] not in order:
            continue
        t = tot[a["player"]]
        t["presenze"] += 1
        t["titolari"] += int(bool(a["started"]))
        if a["minutes"] is None:
            t["minutes_unknown"] += 1
        else:
            t["minuti"] += a["minutes"]
        t["gol"] += a["goals"]; t["assist"] += a["assists"]
        t["club"] = a["club"]
        t["per_match"][a["match"]] = (a["minutes"], a["goals"], a["assists"], bool(a["started"]))
    return tot


def standings(matches, teams):
    """Points, goal difference, goals for, name (the convention of the public tables used in Release 01;
    head-to-head is applied by the league only at season end)."""
    T = {t: dict(pt=0, gf=0, gs=0, g=0) for t in teams}
    for m in matches:
        h, a, hg, ag = m["home"], m["away"], m["hg"], m["ag"]
        for t, f, s in ((h, hg, ag), (a, ag, hg)):
            T[t]["g"] += 1; T[t]["gf"] += f; T[t]["gs"] += s
            T[t]["pt"] += 3 if f > s else 1 if f == s else 0
    def h2h(group):
        r = {t: [0, 0] for t in group}
        for m in matches:
            if m["home"] in group and m["away"] in group:
                for t, f, s in ((m["home"], m["hg"], m["ag"]), (m["away"], m["ag"], m["hg"])):
                    r[t][0] += 3 if f > s else 1 if f == s else 0; r[t][1] += f - s
        return r
    by_pt = defaultdict(list)
    for t in teams:
        by_pt[T[t]["pt"]].append(t)
    order = []
    for pt in sorted(by_pt, reverse=True):
        g = by_pt[pt]
        order += sorted(g, key=lambda t: (-(T[t]["gf"] - T[t]["gs"]), -T[t]["gf"], teams[t]))
    for i, t in enumerate(order, 1):
        T[t]["pos"] = i
    return T


def _val(f, pm):
    if pm is None:
        return None
    mn, g, as_, st = pm
    return {"minuti": mn, "gol": g, "assist": as_, "presenze": 1, "titolari": int(st)}[f]


def load_evidence(path):
    """Manual per-player totals (older format; match sheets are read by evidence.py).
    CSV columns: nome, club, field (minuti|gol|assist|presenze|titolari), value, source_type
    (tabellino|cronaca|other), url, note."""
    ev = defaultdict(list)
    if path and Path(path).exists() and not evidence_mod.is_sheet_file(path):
        for r in csv.DictReader(open(path)):
            ev[(identity.norm(r["nome"]), r["field"])].append(r)
    return ev


def run(out, cfg, universe=None, coverage_mode="strict", evidence=None):
    out = Path(out)
    src = load(out)
    tm, ss = src["tm"], src.get("sofascore")
    meth = cfg["method"]
    audit, idlog = [], []

    def log(kind, **kw):
        audit.append(dict(kind=kind, **kw))

    names = {cid: cfg["club_names"].get(int(cid), n) for cid, n in tm["clubs"].items()}
    # ---- clubs and matches ------------------------------------------------------------
    cmap = identity.match_clubs(tm["clubs"], ss["clubs"]) if ss else {}
    for t, (s, sc) in cmap.items():
        idlog.append(dict(kind="club", tm_id=t, tm_name=tm["clubs"][t], ss_id=s, ss_name=ss["clubs"][s], score=sc, how="name"))
    inv = {s: t for t, (s, _) in cmap.items()}
    ss_by_key = {}
    if ss:
        for m in ss["matches"]:
            ss_by_key[(m["round"], inv.get(m["home"]), inv.get(m["away"]))] = m
    tm_keys = set()
    final_matches = []
    for m in tm["matches"]:
        k = (m["round"], m["home"], m["away"]); tm_keys.add(k)
        o = ss_by_key.get(k)
        mm = dict(m, ss_id=o["id"] if o else None, sources="tm+ss" if o else "tm")
        if o and (o["hg"], o["ag"]) != (m["hg"], m["ag"]):
            log("match_result", match=f"R{m['round']} {names[m['home']]}-{names[m['away']]}",
                tm=f"{m['hg']}-{m['ag']}", ss=f"{o['hg']}-{o['ag']}", decision="TM result kept (conflict logged)",
                url_tm=m["url"], url_ss=o["url"])
        if not o:
            log("match_single_source", match=f"R{m['round']} {names[m['home']]}-{names[m['away']]}", source="tm", url_tm=m["url"])
        final_matches.append(mm)
    for k, o in ss_by_key.items():
        if k not in tm_keys:
            log("match_single_source", match=f"R{o['round']} {o['home']}-{o['away']} (ss ids)", source="sofascore", url_ss=o["url"])
    team_ids = {m["home"] for m in final_matches} | {m["away"] for m in final_matches}
    table = standings(final_matches, {t: names.get(t, t) for t in team_ids})

    # ---- players ----------------------------------------------------------------------
    A_tm, A_ss = aggregate(tm), aggregate(ss) if ss else {}
    ss_match_to_tm = {mm["ss_id"]: mm["id"] for mm in final_matches if mm["ss_id"]}
    match_by_id = {mm["id"]: mm for mm in final_matches}
    no_lu = {str(x) for x in (ss or {}).get("no_lineup", [])}
    uncovered = {mm["id"] for mm in final_matches if not mm["ss_id"] or mm["ss_id"] in no_lu}
    # manual match sheets (data/manual/evidence.csv) replace the missing second source per team
    man_cov, man_val = {}, {}
    if evidence and evidence_mod.is_sheet_file(evidence):
        man_cov, man_val = evidence_mod.build(evidence, tm, names, final_matches, log)
    for mid in sorted(uncovered):
        m = match_by_id[mid]
        teams_cov = [names[c] for c in (m["home"], m["away"]) if (mid, c) in man_cov]
        log("coverage", match=f"R{m['round']} {names[m['home']]}-{names[m['away']]}",
            decision=("second source has no lineup: player figures from this match are single-source"
                      + (f" (except teams with a manual sheet: {', '.join(teams_cov)})" if teams_cov else "")), url_tm=m["url"])
    pairs = {}  # tm_pid -> ss_pid
    for t_cid in team_ids:
        L = {p: tm["players"][p] for p, a in A_tm.items() if a["club"] == t_cid}
        s_cid = cmap.get(t_cid, (None,))[0]
        R = {p: ss["players"][p] for p, a in A_ss.items() if a["club"] == s_cid} if s_cid else {}
        got, ul, ur = identity.match_players(L, R)
        for l, r, sc, how in got:
            pairs[l] = r
            idlog.append(dict(kind="player", club=names.get(t_cid), tm_id=l, tm_name=L[l]["name"], tm_dob=L[l].get("dob"),
                              ss_id=r, ss_name=R[r]["name"], ss_dob=R[r].get("dob"), score=sc, how=how))
        for l in ul:
            idlog.append(dict(kind="player_unmatched", club=names.get(t_cid), tm_id=l, tm_name=L[l]["name"], tm_dob=L[l].get("dob")))
        for r in ur:
            idlog.append(dict(kind="player_unmatched", club=names.get(t_cid), ss_id=r, ss_name=R[r]["name"], ss_dob=R[r].get("dob")))
    # ss-only players are kept only for the audit (no TM role -> cannot be scored)
    ev = load_evidence(evidence)
    app_club = {(x["match"], x["player"]): x["club"] for x in tm["apps"]}
    excl = cfg["exclusions"]
    roles = cfg["roles"]
    rows = []
    for pid, a in A_tm.items():
        p = tm["players"][pid]
        q = ss["players"].get(pairs.get(pid)) if pid in pairs else None
        b = A_ss.get(pairs.get(pid)) if pid in pairs else None
        by_tm, by_ss = p.get("birth_year"), q.get("birth_year") if q else None
        nato = by_tm or by_ss
        if by_tm and by_ss and by_tm != by_ss:
            log("field", player=p["name"], club=names.get(a["club"]), field="nato", tm=by_tm, ss=by_ss,
                decision="TM kept (profile date of birth)", confidence="bassa")
        if nato is None or nato < meth["min_birth_year"]:
            continue
        ruolo = roles.get(p.get("position") or "", "?")
        if ruolo == "GK":
            continue
        if ruolo == "?":
            log("role_missing", player=p["name"], club=names.get(a["club"]), decision="no Transfermarkt main position: not written to CSV (role is a TM-only field by method)")
            continue
        row = dict(nome=p["name"], nato=nato, ruolo=ruolo, club=names.get(a["club"], a["club"]),
                   _tm=pid, _ss=pairs.get(pid), _pos_tm=p.get("position"))
        # matches without SofaScore lineup where this player's team (in that match) has a manual sheet
        def _club(mid):
            return app_club.get((mid, pid), a["club"])
        man_mids = [mid for mid in uncovered if (mid, _club(mid)) in man_cov]
        for f in FIELDS:
            va = a[f] if not (f == "minuti" and a["minutes_unknown"]) else None
            vb = b[f] if b and not (f == "minuti" and b["minutes_unknown"]) else None
            # a manual sheet covers field f for a match if the sheet gives that value
            # (assists can be "not reported"; minutes unknown if a sub/red minute is missing)
            cov_f = [mid for mid in man_mids
                     if not ((f == "assist" and not man_cov[(mid, _club(mid))]["assists_known"])
                             or (f == "minuti" and (mid, pid) in man_val and man_val[(mid, pid)][0] is None))]
            man_sum = sum(_val(f, man_val.get((mid, pid))) or 0 for mid in cov_f)
            if cov_f:
                if vb is not None:
                    vb = vb + man_sum
                elif b is None and all(mid in cov_f for mid in a["per_match"]):
                    vb = man_sum   # player only ever seen in matches covered by a sheet
            unc = [mid for mid in a["per_match"] if mid in uncovered and mid not in cov_f]
            part = sum(_val(f, a["per_match"][mid]) or 0 for mid in unc)
            if unc and va is not None and vb is not None:
                # second source has no lineup for some matches of this player: compare on the
                # matches both sources cover; the rest is single-source.
                v0, st0, conf0, gap = rules.apply(f, va - part, vb, meth["max_gap_goals_assists"], meth["max_gap_minutes"])
                v = v0 + part
                st = "partial" if part else st0
                conf = "bassa" if (part and coverage_mode == "strict") else conf0
            else:
                v, st, conf, gap = rules.apply(f, va, vb, meth["max_gap_goals_assists"], meth["max_gap_minutes"])
            for e in ev.get((identity.norm(p["name"]), f), []):
                x = int(e["value"]); official = e.get("source_type") in ("tabellino", "cronaca")
                agrees = [s_ for s_ in (va, vb) if s_ is not None and s_ == x]
                if agrees:
                    old = (v, conf)
                    v, conf = x, ("alta" if official else "media")
                    st = "confirmed_evidence"
                    log("evidence", player=p["name"], club=row["club"], field=f, tm=va, ss=vb, decision=f"{v}",
                        confidence=conf, per_match=f"manual {e.get('source_type')} = {x} (was {old})", url_tm=e.get("url", ""))
                else:
                    log("evidence", player=p["name"], club=row["club"], field=f, tm=va, ss=vb, decision=f"{v}",
                        confidence=conf, per_match=f"manual value {x} agrees with no automated source; not applied",
                        url_tm=e.get("url", ""))
            row[f] = v
            if f in KEY:
                row[KEY[f]] = conf
            if st not in ("confirmed", "confirmed_evidence"):
                diffs = []
                b_ = b or {"per_match": {}}
                if a:
                    for mid, pm in a["per_match"].items():
                        m = match_by_id[mid]
                        if mid in cov_f:
                            vm = _val(f, man_val[(mid, pid)]) if (mid, pid) in man_val else 0  # not in sheet = did not play
                            if _val(f, pm) != vm:
                                diffs.append(f"R{m['round']} {names[m['home']]}-{names[m['away']]}: tm {_val(f, pm)} manual {vm}")
                            continue
                        if mid in uncovered:
                            diffs.append(f"R{m['round']} {names[m['home']]}-{names[m['away']]}: tm {_val(f, pm)} ss no-lineup")
                            continue
                        o = b_["per_match"].get(m["ss_id"])
                        vt, vs = _val(f, pm), _val(f, o) if o else (0 if f != "minuti" else None)
                        if vt != vs:
                            diffs.append(f"R{m['round']} {names[m['home']]}-{names[m['away']]}: tm {vt} ss {vs}")
                    for (mmid, mpid), mv in man_val.items():
                        if mpid == pid and mmid in cov_f and mmid not in a["per_match"]:
                            m = match_by_id[mmid]
                            diffs.append(f"R{m['round']} {names[m['home']]}-{names[m['away']]}: tm not-in-lineup manual {_val(f, mv)}")
                    for smid, o in b_["per_match"].items():
                        if ss_match_to_tm.get(smid) not in a["per_match"]:
                            m = match_by_id.get(ss_match_to_tm.get(smid))
                            lab = f"R{m['round']} {names[m['home']]}-{names[m['away']]}" if m else f"ss event {smid}"
                            diffs.append(f"{lab}: tm not-in-lineup ss {_val(f, o)}")
                log("field", player=p["name"], club=row["club"], field=f, tm=va, ss=vb, gap=gap, status=st,
                    tm_only_part=part if unc else "", decision=f"{v}", confidence=conf if f in KEY else "-",
                    per_match="; ".join(diffs),
                    url_tm=f"https://www.transfermarkt.it/x/profil/spieler/{pid}",
                    url_ss=(q or {}).get("url", ""))
        T = table[a["club"]]
        row.update(pos_classifica=T["pos"], partite_squadra=T["g"], gs_squadra=T["gs"])
        for col, rule in excl.items():
            flagged = int(a["club"]) in rule.get("tm_club_ids", []) or f"{p['name']}|{row['club']}" in rule.get("players", [])
            row[col] = int(flagged)
        rows.append(row)
    # ---- universe ---------------------------------------------------------------------
    if universe:
        ref = list(csv.DictReader(open(universe)))
        keep, missing = [], []
        for r in ref:
            best = max(rows, key=lambda x: identity.name_score(x["nome"], r["nome"]) + (0.2 if identity.norm(x["club"]) == identity.norm(r["club"]) else 0), default=None)
            if best and identity.name_score(best["nome"], r["nome"]) >= 0.85:
                best["_ref_name"] = r["nome"]; keep.append(best)
            else:
                missing.append(r["nome"])
        for n in missing:
            log("universe_missing", player=n, decision="reference player not found in agent data")
        rows = keep
    cols = config_mod.output_columns(cfg)
    rows.sort(key=lambda r: (r["club"], r["nome"]))
    with open(out / "reconciled.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore"); w.writeheader(); w.writerows(rows)
    with open(out / "reconciled_ids.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["nome", "club", "_tm", "_ss", "_pos_tm", "_ref_name"], extrasaction="ignore")
        w.writeheader(); w.writerows(rows)
    keys = sorted({k for r in audit for k in r}, key=lambda k: ["kind", "player", "match", "club", "field"].index(k) if k in ["kind", "player", "match", "club", "field"] else 9)
    with open(out / "audit_log.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys); w.writeheader(); w.writerows(audit)
    ik = sorted({k for r in idlog for k in r})
    with open(out / "identity_log.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=ik); w.writeheader(); w.writerows(idlog)
    st = dict(coverage_mode=coverage_mode, matches_uncovered=len(uncovered), matches_tm=len(tm["matches"]), matches_ss=len(ss["matches"]) if ss else 0,
              clubs_matched=len(cmap), players_matched=len(pairs), rows=len(rows), audit_entries=len(audit),
              conflicts=sum(1 for x in audit if x["kind"] == "field"))
    (out / "summary.json").write_text(json.dumps(dict(st, standings={names.get(t, t): v for t, v in table.items()}), ensure_ascii=False, indent=1))
    return st
