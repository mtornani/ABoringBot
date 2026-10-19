"""Transfermarkt: fixtures (gesamtspielplan), match reports (spielbericht), squads (kader).

Minutes are derived from the match report the way Transfermarkt counts them: starter 90',
subbed off at m -> m, subbed on at m -> 90-m, sent off at m -> minutes up to m.
"""
import re
from bs4 import BeautifulSoup

BASE = "https://www.transfermarkt.it"
VEREIN = re.compile(r"/verein/(\d+)")
SPIELER = re.compile(r"/spieler/(\d+)")


def sprite_minute(span):
    """Decode the minute from Transfermarkt's clock sprite (10 x N grid of 36px cells)."""
    if span is None:
        return None
    txt = span.get_text(strip=True)
    m = re.match(r"(\d+)'?\s*\+?\s*(\d+)?", txt)
    if txt and m:
        return int(m.group(1))
    st = span.get("style", "")
    m = re.search(r"background-position:\s*-?(\d+)px\s+-?(\d+)px", st)
    if not m:
        return None
    x, y = int(m.group(1)), int(m.group(2))
    if x % 36 or y % 36:
        return None          # placeholder sprite (minute not recorded)
    return (y // 36) * 10 + (x // 36) + 1


def parse_fixtures(html):
    s = BeautifulSoup(html, "lxml")
    out = []
    for box in s.select("div.box"):
        h = box.find(class_=re.compile("headline"))
        m = re.match(r"(\d+)\.\s*Giornata", h.get_text(strip=True)) if h else None
        if not m:
            continue
        rnd, date = int(m.group(1)), None
        for tr in box.select("tr"):
            dm = re.search(r"\d{2}/\d{2}/\d{2}", tr.get_text(" "))
            if dm:
                date = dm.group(0)
            a = tr.find("a", href=re.compile(r"/spielbericht/\d+"))
            if not a:
                continue
            ids = [int(x) for x in VEREIN.findall(str(tr))]
            ids = list(dict.fromkeys(ids))
            res = re.match(r"\s*(\d+):(\d+)", a.get_text())
            mid = int(re.search(r"/spielbericht/(\d+)", a["href"]).group(1))
            if len(ids) < 2:
                continue
            out.append(dict(id=mid, round=rnd, date=date, home=ids[0], away=ids[1],
                            hg=int(res.group(1)) if res else None, ag=int(res.group(2)) if res else None,
                            url=f"{BASE}/spielbericht/index/spielbericht/{mid}"))
    return out


def _club_of(li):
    a = li.find(class_="sb-aktion-wappen")
    a = a.find("a", href=VEREIN) if a else None
    return int(VEREIN.search(a["href"]).group(1)) if a else None


def parse_report(html, match):
    s = BeautifulSoup(html, "lxml")
    side = {}
    for c in ("sb-heim", "sb-gast"):
        d = s.find(class_=c)
        a = d.find("a", href=VEREIN) if d else None
        side[c] = int(VEREIN.search(a["href"]).group(1)) if a else None
    home, away = side["sb-heim"] or match["home"], side["sb-gast"] or match["away"]
    names, starters = {}, {}
    boxes = s.select("div.aufstellung-box") + [b for b in s.select("div.large-6.columns")
                                               if b.select(".formation-player-container") and "aufstellung-box" not in b.get("class", [])]
    for box in boxes[:2]:
        a = box.find("a", href=VEREIN)
        cid = int(VEREIN.search(a["href"]).group(1)) if a else None
        for fc in box.select(".formation-player-container a[href*='/spieler/']"):
            pid = int(SPIELER.search(fc["href"]).group(1))
            starters[pid] = cid
            names.setdefault(pid, fc.get_text(strip=True))
    # fallback: table-style lineups
    if not starters:
        for i, box in enumerate(s.select("div.aufstellung-vereinsseite, table.aufstellung-vereinsseite")[:2]):
            for a in box.find_all("a", href=re.compile(r"/profil/spieler/")):
                starters[int(SPIELER.search(a["href"]).group(1))] = home if i == 0 else away
    on, off, red = {}, {}, {}
    sw = s.find(id="sb-wechsel")
    for li in (sw.find_all("li") if sw else []):
        mnt = sprite_minute(li.find(class_="sb-sprite-uhr-klein"))
        cid = _club_of(li) or (home if "sb-aktion-heim" in li.get("class", []) else away)
        ein = li.find(class_="sb-aktion-wechsel-ein")
        aus = li.find(class_="sb-aktion-wechsel-aus")
        if ein and ein.find("a", href=SPIELER):
            a = ein.find("a", href=SPIELER); pid = int(SPIELER.search(a["href"]).group(1))
            on[pid] = (mnt, cid); names.setdefault(pid, a.get("title") or a.get_text(strip=True))
        if aus and aus.find("a", href=SPIELER):
            a = aus.find("a", href=SPIELER); pid = int(SPIELER.search(a["href"]).group(1))
            off[pid] = mnt; names.setdefault(pid, a.get("title") or a.get_text(strip=True))
    sk = s.find(id="sb-karten")
    for li in (sk.find_all("li") if sk else []):
        t = li.get_text(" ", strip=True).lower()
        if "rosso" in t or "giallo/rosso" in t or "doppia" in t or "espuls" in t:
            a = li.find(class_="sb-aktion-aktion").find("a", href=SPIELER)
            if a:
                red[int(SPIELER.search(a["href"]).group(1))] = sprite_minute(li.find(class_="sb-sprite-uhr-klein"))
    goals, assists = {}, {}
    st = s.find(id="sb-tore")
    for li in (st.find_all("li") if st else []):
        akt = li.find(class_="sb-aktion-aktion")
        if not akt:
            continue
        links = akt.find_all("a", href=SPIELER)
        txt = akt.get_text(" ", strip=True).lower()
        own = "autogol" in txt or "autorete" in txt
        if links and not own:
            g = int(SPIELER.search(links[0]["href"]).group(1)); goals[g] = goals.get(g, 0) + 1
        if "assist" in txt and len(links) > 1:
            a = int(SPIELER.search(links[1]["href"]).group(1)); assists[a] = assists.get(a, 0) + 1
    apps, notes = [], []
    for pid in set(starters) | set(on):
        st_ = pid in starters
        cid = starters.get(pid) or on[pid][1]
        start = 0 if st_ else on[pid][0]
        end = off.get(pid, 90) if pid in off else 90
        if pid in red:
            end = red[pid] if red[pid] is not None else end
            if red[pid] is None:
                notes.append(f"red card minute unknown for player {pid}")
        if start is None or end is None:
            notes.append(f"minute unknown for player {pid}")
            mins = None
        else:
            mins = max(0, min(end, 90) - min(start, 90))
            if not st_ and mins == 0:
                mins = 1      # Transfermarkt credits 1' to a substitute who comes on in added time
        apps.append(dict(match=match["id"], player=pid, club=cid, started=st_, minutes=mins,
                         goals=goals.get(pid, 0), assists=assists.get(pid, 0)))
    return apps, names, notes


def parse_squad(html, club_id):
    """kader/plus/1: name, date of birth, main position for every squad member."""
    s = BeautifulSoup(html, "lxml")
    out = {}
    t = s.find("table", class_="items")
    if not t:
        return out
    for tr in t.find("tbody").find_all("tr", recursive=False):
        a = tr.select_one("td.hauptlink a[href*='/spieler/']")
        if not a:
            continue
        pid = int(SPIELER.search(a["href"]).group(1))
        inl = tr.find("table", class_="inline-table")
        pos = inl.find_all("tr")[-1].get_text(strip=True) if inl else None
        dob = None
        for td in tr.find_all("td", recursive=False):
            m = re.search(r"(\d{2})/(\d{2})/(\d{4})", td.get_text())
            if m:
                dob = f"{m.group(3)}-{m.group(2)}-{m.group(1)}"; break
        out[pid] = dict(name=a.get_text(strip=True), dob=dob,
                        birth_year=int(dob[:4]) if dob else None, position=pos, club=club_id)
    return out


def parse_profile(html):
    s = BeautifulSoup(html, "lxml")
    pos = s.select_one(".detail-position__position")
    pos = pos.get_text(strip=True) if pos else None
    if not pos:
        for lab in s.select(".data-header__label"):
            t = lab.get_text(" ", strip=True)
            if t.startswith("Posizione:"):
                pos = t.split(":", 1)[1].strip()
    dob = None
    b = s.find(attrs={"itemprop": "birthDate"})
    m = re.search(r"(\d{2})/(\d{2})/(\d{4})", b.get_text()) if b else None
    if m:
        dob = f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
    h = s.find("h1")
    name = " ".join(h.get_text(" ", strip=True).replace("#", " ").split()) if h else None
    if name:
        name = re.sub(r"^\d+\s+", "", name)
    return dict(name=name, dob=dob, birth_year=int(dob[:4]) if dob else None, position=pos)


def collect(fetcher, cfg, max_round, log=print):
    c = cfg["competition"]
    fx_url = f"{BASE}/{c['tm_slug']}/gesamtspielplan/wettbewerb/{c['tm_code']}/saison_id/{c['season']}"
    fixtures = parse_fixtures(fetcher.get(fx_url))
    matches = [m for m in fixtures if m["round"] <= max_round and m["hg"] is not None]
    log(f"[tm] {len(fixtures)} fixtures, {len(matches)} played in rounds <= {max_round}")
    apps, names, notes = [], {}, []
    for m in matches:
        a, n, nt = parse_report(fetcher.get(m["url"]), m)
        apps += a; names.update(n); notes += [f"match {m['id']}: {x}" for x in nt]
        if not a:
            notes.append(f"match {m['id']}: no lineup on report")
    club_ids = sorted({m["home"] for m in fixtures} | {m["away"] for m in fixtures})
    players, clubs = {}, {}
    for cid in club_ids:
        url = f"{BASE}/x/kader/verein/{cid}/saison_id/{c['season']}/plus/1"
        html = fetcher.get(url)
        h = BeautifulSoup(html, "lxml").find("h1")
        clubs[cid] = h.get_text(" ", strip=True) if h else str(cid)
        players.update(parse_squad(html, cid))
    # players who appeared but are no longer in a squad list (moved on): read their profile
    missing = sorted({a["player"] for a in apps} - set(players))
    for pid in missing:
        try:
            pr = parse_profile(fetcher.get(f"{BASE}/x/profil/spieler/{pid}"))
        except RuntimeError:
            pr = dict(name=None, dob=None, birth_year=None, position=None)
        pr["name"] = pr["name"] or names.get(pid)
        pr["club"] = None
        players[pid] = pr
    log(f"[tm] {len(missing)} profiles fetched for players not in current squad lists")
    return dict(source="tm", clubs=clubs, matches=matches, players=players, apps=apps, notes=notes,
                urls=dict(fixtures=fx_url))
