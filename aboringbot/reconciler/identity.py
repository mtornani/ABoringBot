"""Identity matching across sources: name normalization, birth date, club."""
import re, unicodedata
from difflib import SequenceMatcher

STOP_CLUB = {"calcio", "asd", "ssd", "fc", "ac", "us", "usd", "ss", "fbc", "gs", "sc", "aurora", "srl", "a", "d",
             "citta", "di", "1913", "1919", "1907", "1908", "1921", "1926", "1948", "1911", "vis", "sd"}


def norm(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-z ]+", " ", s.lower())
    return " ".join(s.split())


def tokens(s):
    return set(norm(s).split())


def club_key(s):
    return {t for t in tokens(s) if t not in STOP_CLUB and not t.isdigit()}


def club_similarity(a, b):
    ka, kb = club_key(a), club_key(b)
    j = len(ka & kb) / max(1, len(ka | kb))
    return max(j, SequenceMatcher(None, " ".join(sorted(ka)), " ".join(sorted(kb))).ratio() * 0.9)


def name_score(a, b):
    """0..1 similarity of two person names (token aware, accent/case insensitive)."""
    na, nb = norm(a), norm(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    ta, tb = set(na.split()), set(nb.split())
    small, big = (ta, tb) if len(ta) <= len(tb) else (tb, ta)
    if small <= big:
        return 0.95                       # "Orso De Ponti" vs "Orso Maria De Ponti"
    inter = ta & tb
    tok = len(inter) / len(ta | tb)
    return max(tok, SequenceMatcher(None, na, nb).ratio() * 0.95)


def match_players(left, right, min_score=0.6):
    """Greedy 1:1 matching within a club.

    left/right: {id: {name, dob}}. Same date of birth is strong evidence; a name score of
    0.85+ alone is accepted; 0.6-0.85 needs the same birth date.
    Returns list of (lid, rid, score, how) and the unmatched ids of both sides.
    """
    cand = []
    for li, l in left.items():
        for ri, r in right.items():
            ns = name_score(l["name"], r["name"])
            same_dob = bool(l.get("dob")) and l.get("dob") == r.get("dob")
            if ns >= 0.85:
                cand.append((ns + (0.1 if same_dob else 0), li, ri, "name" + ("+dob" if same_dob else "")))
            elif ns >= min_score and same_dob:
                cand.append((ns + 0.1, li, ri, "dob+partial-name"))
    cand.sort(key=lambda x: -x[0])
    used_l, used_r, out = set(), set(), []
    for s, li, ri, how in cand:
        if li in used_l or ri in used_r:
            continue
        used_l.add(li); used_r.add(ri); out.append((li, ri, round(s, 3), how))
    return out, [i for i in left if i not in used_l], [i for i in right if i not in used_r]


def match_clubs(a, b):
    """a, b: {id: name}. Greedy 1:1 by club-name similarity."""
    cand = sorted(((club_similarity(na, nb), ia, ib) for ia, na in a.items() for ib, nb in b.items()),
                  key=lambda x: -x[0])
    ua, ub, out = set(), set(), {}
    for s, ia, ib in cand:
        if ia in ua or ib in ub or s < 0.3:
            continue
        ua.add(ia); ub.add(ib); out[ia] = (ib, round(s, 3))
    return out
