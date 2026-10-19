"""Manual evidence: match sheets read by a human from public match reports (tabellini).

File: data/manual/evidence.csv, one row per player who took part in a match, for matches where an
automated source is missing. Columns:

  round, date, home, away   match key (club names as in config [club_names] / Transfermarkt)
  team                      club of the player (home or away)
  player                    name as written in the source (surname is enough within a team)
  started                   1 = starting XI, 0 = substitute who came on
  sub_on, sub_off, red_card minute text as written in the source: "66'", "35' st", "11' pt", blank = none,
                            "?" = event happened but the minute is not given (minutes unknown)
  goals                     goals scored (integer)
  assists                   integer, or blank = the source does not say who assisted (field not covered)
  source_type               tabellino | cronaca | other
  source_url, retrieved     public URL and retrieval date (YYYY-MM-DD); required on every row
  note                      free text (other sources consulted, spellings, conflicts)

A team listed for a match is a complete sheet: a player of that team who is not listed did not play.
Minutes follow the convention of the collectors (nominal minute, match = 90', added-time substitute = 1').

The older per-player total format (columns nome, club, field, value, source_type, url, note) is still read
by reconcile.load_evidence; the two formats are told apart by the header.
"""
import csv, re
from pathlib import Path

from . import identity

MIN_RE = re.compile(r"^\s*(\d+)\s*(?:'|’|′)?\s*(?:\+\s*(\d+))?\s*(pt|st|1t|2t)?\s*$", re.I)
SHEET_COLS = {"round", "home", "away", "team", "player", "started", "goals", "assists", "source_url", "retrieved"}


class EvidenceError(ValueError):
    pass


def parse_minute(txt):
    """Minute text -> nominal minute (int), None for blank, 'unknown' for '?'.
    "35' st" -> 80; "11' pt" -> 11; "66'" -> 66; "48' st" -> 93 (added time; capped later)."""
    if txt is None or not str(txt).strip():
        return None
    t = str(txt).strip()
    if t == "?":
        return "unknown"
    m = MIN_RE.match(t)
    if not m:
        raise EvidenceError(f"unreadable minute {txt!r}")
    v = int(m.group(1)) + int(m.group(2) or 0)
    half = (m.group(3) or "").lower()
    if half in ("st", "2t"):
        v += 45
    return v


def minutes(started, on, off, red):
    """Same convention as the collectors; None if a needed minute is unknown."""
    if "unknown" in (on, off, red):
        return None
    start = 0 if started else on
    if start is None:
        raise EvidenceError("substitute without sub_on minute")
    ends = [x for x in (off, red) if x is not None]
    end = min(ends) if ends else 90
    m = max(0, min(end, 90) - min(start, 90))
    return 1 if (not started and m == 0) else m


def is_sheet_file(path):
    if not path or not Path(path).exists():
        return False
    with open(path, newline="") as f:
        head = next(csv.reader(f), [])
    return SHEET_COLS <= set(head)


def read_sheets(path):
    """Rows -> list of dicts with parsed minutes. Raises EvidenceError on malformed rows."""
    out = []
    with open(path, newline="") as f:
        for i, r in enumerate(csv.DictReader(f), 2):
            if not r.get("source_url", "").startswith("http") or not re.match(r"\d{4}-\d{2}-\d{2}$", r.get("retrieved", "")):
                raise EvidenceError(f"line {i}: source_url and retrieved (YYYY-MM-DD) are required")
            st = r["started"].strip() == "1"
            on, off, red = (parse_minute(r.get(k)) for k in ("sub_on", "sub_off", "red_card"))
            a = r.get("assists", "").strip()
            out.append(dict(r, line=i, round=int(r["round"]), started=st, minutes=minutes(st, on, off, red),
                            goals=int(r["goals"] or 0), assists=int(a) if a != "" else None))
    return out


def surname_score(src, full):
    """Score a source name (often surname only, maybe with an initial) against a full name."""
    toks = [t for t in identity.norm(src).split() if len(t) > 1]
    ft = identity.norm(full).split()
    if not toks or not ft:
        return 0.0
    if identity.norm(src) == identity.norm(full):
        return 1.0
    if all(t in ft for t in toks):
        return 0.95
    from difflib import SequenceMatcher
    last = " ".join(toks)
    best = max(SequenceMatcher(None, last, " ".join(ft[k:])).ratio() for k in range(len(ft)))
    best = max(best, max(SequenceMatcher(None, t, f).ratio() for t in toks for f in ft) * 0.95)
    if any(t in ft for t in toks):
        best = max(best, 0.9)
    return best


def match_sheet_players(sheet_rows, candidates, min_score=0.85):
    """sheet_rows: rows of one team in one match; candidates: {pid: name}. Greedy 1:1.
    Returns {line: (pid, score)} and the unmatched rows."""
    cand = sorted(((surname_score(r["player"], n), r["line"], pid) for r in sheet_rows for pid, n in candidates.items()),
                  key=lambda x: -x[0])
    used_r, used_p, got = set(), set(), {}
    for s, line, pid in cand:
        if s < min_score or line in used_r or pid in used_p:
            continue
        # ambiguous: another candidate with the same top score for this row
        ties = [c for c in cand if c[1] == line and c[0] == s and c[2] not in used_p]
        if len(ties) > 1:
            continue
        used_r.add(line); used_p.add(pid); got[line] = (pid, round(s, 3))
    return got, [r for r in sheet_rows if r["line"] not in used_r]


def build(path, tm, names, final_matches, log):
    """Match the sheets to Transfermarkt matches and players.

    Returns (covered, values):
      covered: {(tm_match_id, tm_club_id): row-meta} for every team sheet found
      values:  {(tm_match_id, tm_pid): (minutes|None, goals, assists|None, started)}
    """
    rows = read_sheets(path)
    by_name = {identity.norm(n): cid for cid, n in names.items()}
    for cid, n in tm["clubs"].items():
        by_name.setdefault(identity.norm(n), cid)

    def club(n):
        k = identity.norm(n)
        if k in by_name:
            return by_name[k]
        best = max(by_name, key=lambda x: identity.club_similarity(x, k))
        if identity.club_similarity(best, k) < 0.5:
            raise EvidenceError(f"unknown club {n!r}")
        return by_name[best]

    mkey = {(m["round"], m["home"], m["away"]): m for m in final_matches}
    groups = {}
    for r in rows:
        k = (r["round"], club(r["home"]), club(r["away"]))
        if k not in mkey:
            raise EvidenceError(f"line {r['line']}: no Transfermarkt match R{r['round']} {r['home']}-{r['away']}")
        groups.setdefault((mkey[k]["id"], club(r["team"])), []).append(r)
    covered, values = {}, {}
    for (mid, cid), rs in groups.items():
        m = next(x for x in final_matches if x["id"] == mid)
        lab = f"R{m['round']} {names.get(m['home'])}-{names.get(m['away'])} [{names.get(cid)}]"
        nst = sum(r["started"] for r in rs)
        if nst != 11:
            log("evidence_check", match=lab, decision=f"sheet lists {nst} starters (expected 11)", url_tm=rs[0]["source_url"])
        cands = {pid: p["name"] for pid, p in tm["players"].items() if str(p.get("club")) == str(cid)}
        for a in tm["apps"]:
            if a["club"] == cid:
                cands.setdefault(a["player"], tm["players"][a["player"]]["name"])
        got, miss = match_sheet_players(rs, cands)
        for r in miss:
            log("evidence_unmatched", match=lab, player=r["player"],
                decision="sheet player not matched to a Transfermarkt player of this club: not used", url_tm=r["source_url"])
        for r in rs:
            if r["line"] in got:
                pid = got[r["line"]][0]
                values[(mid, pid)] = (r["minutes"], r["goals"], r["assists"], r["started"])
        goals_sheet = sum(r["goals"] for r in rs)
        tgoals = m["hg"] if cid == m["home"] else m["ag"]
        if goals_sheet > tgoals:
            log("evidence_check", match=lab, decision=f"sheet goals {goals_sheet} > team goals {tgoals} in result",
                url_tm=rs[0]["source_url"])
        covered[(mid, cid)] = dict(url=rs[0]["source_url"], retrieved=rs[0]["retrieved"],
                                   assists_known=all(r["assists"] is not None for r in rs),
                                   matched=len(got), rows=len(rs))
        log("coverage_manual", match=lab,
            decision=f"manual match sheet ({rs[0]['source_type']}, retrieved {rs[0]['retrieved']}): second source for this team; "
                     f"{len(got)}/{len(rs)} players matched; assists {'covered' if covered[(mid, cid)]['assists_known'] else 'not reported'}",
            url_tm=rs[0]["source_url"])
    return covered, values
