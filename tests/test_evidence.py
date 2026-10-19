import csv, json

import pytest

from aboringbot import config
from aboringbot.reconciler import evidence as E, reconcile


def test_parse_minute():
    assert E.parse_minute("66'") == 66
    assert E.parse_minute("35' st") == 80
    assert E.parse_minute("11’pt") == 11
    assert E.parse_minute("48′ st") == 93
    assert E.parse_minute("") is None
    assert E.parse_minute("?") == "unknown"
    with pytest.raises(E.EvidenceError):
        E.parse_minute("st")


def test_minutes_convention():
    assert E.minutes(True, None, None, None) == 90
    assert E.minutes(True, None, 80, None) == 80
    assert E.minutes(False, 80, None, None) == 10
    assert E.minutes(False, 93, None, None) == 1          # added-time substitute
    assert E.minutes(False, 90, None, None) == 1
    assert E.minutes(False, 73, None, 75) == 2           # came on, then sent off
    assert E.minutes(True, None, None, "unknown") is None


def test_surname_matching():
    c = {"1": "Elia Maccherini Tonini", "2": "Matteo Motti", "3": "Simone Saporetti", "4": "Lorenzo Saporetti"}
    rows = [dict(line=2, player="Maccherini"), dict(line=3, player="Motti M."), dict(line=4, player="Saporetti")]
    got, miss = E.match_sheet_players(rows, c)
    assert got[2][0] == "1" and got[3][0] == "2"
    assert [r["player"] for r in miss] == ["Saporetti"]   # ambiguous surname is not guessed


def _src(path, ss_lineup_m2):
    clubs = {"1": "Alpha FC", "2": "Beta FC"}
    matches = [dict(id=10, round=1, date="01/09/26", home=1, away=2, hg=1, ag=0, url="u10"),
               dict(id=11, round=2, date="08/09/26", home=2, away=1, hg=0, ag=1, url="u11")]
    players = {"100": dict(name="Mario Rossi", dob="2005-01-01", birth_year=2005, position="Terzino destro", club=1),
               "101": dict(name="Luca Bianchi", dob="2004-01-01", birth_year=2004, position="Punta centrale", club=1),
               "200": dict(name="Paolo Verdi", dob="2003-01-01", birth_year=2003, position="Mediano", club=2)}
    def app(m, p, c, st, mn, g=0, a=0):
        return dict(match=m, player=p, club=c, started=st, minutes=mn, goals=g, assists=a)
    tm = dict(source="tm", clubs=clubs, matches=matches, players=players, notes=[], urls=[], apps=[
        app(10, 100, 1, True, 90, 0, 1), app(10, 101, 1, True, 70, 1, 0), app(10, 200, 2, True, 90),
        app(11, 100, 1, True, 90, 0, 1), app(11, 101, 1, True, 60, 1, 0), app(11, 200, 2, True, 90)])
    ssp = {"9100": dict(name="Mario Rossi", dob="2005-01-01", birth_year=2005, url="s"),
           "9101": dict(name="Luca Bianchi", dob="2004-01-01", birth_year=2004, url="s"),
           "9200": dict(name="Paolo Verdi", dob="2003-01-01", birth_year=2003, url="s")}
    ss = dict(source="sofascore", clubs={"91": "Alpha", "92": "Beta"}, players=ssp, notes=[], urls=[],
              matches=[dict(id=810, round=1, date="", home=91, away=92, hg=1, ag=0, url="s810"),
                       dict(id=811, round=2, date="", home=92, away=91, hg=0, ag=1, url="s811")],
              no_lineup=[] if ss_lineup_m2 else [811],
              apps=[app(810, 9100, 91, True, 90, 0, 1), app(810, 9101, 91, True, 70, 1, 0), app(810, 9200, 92, True, 90)])
    (path / "source_tm.json").write_text(json.dumps(tm))
    (path / "source_sofascore.json").write_text(json.dumps(ss))


def _sheet(path, assists="0", bianchi_off="15' st"):
    cols = ["round", "date", "home", "away", "team", "player", "started", "sub_on", "sub_off", "red_card", "goals",
            "assists", "source_type", "source_url", "retrieved", "note"]
    base = dict(round=2, date="2026-09-08", home="Beta FC", away="Alpha FC", team="Alpha FC", red_card="",
                source_type="tabellino", source_url="https://example.org/r2", retrieved="2026-10-19", note="", sub_on="")
    rows = [dict(base, player="Rossi", started=1, sub_off="", goals=0, assists=assists),
            dict(base, player="Bianchi", started=1, sub_off=bianchi_off, goals=1, assists=assists)]
    rows += [dict(base, player=f"Extra{i}", started=1, sub_off="", goals=0, assists=assists) for i in range(9)]
    p = path / "evidence.csv"
    with open(p, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols); w.writeheader(); w.writerows(rows)
    return p


def _rows(out):
    return {r["nome"]: r for r in csv.DictReader(open(out / "reconciled.csv"))}


def test_no_lineup_match_is_single_source(tmp_path):
    _src(tmp_path, ss_lineup_m2=False)
    reconcile.run(tmp_path, config.load())
    r = _rows(tmp_path)
    assert r["Mario Rossi"]["minuti"] == "180" and r["Mario Rossi"]["conf_minuti"] == "bassa"


def test_manual_sheet_covers_missing_lineup(tmp_path):
    _src(tmp_path, ss_lineup_m2=False)
    ev = _sheet(tmp_path)
    reconcile.run(tmp_path, config.load(), evidence=ev)
    r = _rows(tmp_path)
    assert (r["Mario Rossi"]["minuti"], r["Mario Rossi"]["conf_minuti"]) == ("180", "media")
    assert (r["Luca Bianchi"]["minuti"], r["Luca Bianchi"]["conf_minuti"]) == ("130", "media")
    assert (r["Luca Bianchi"]["gol"], r["Luca Bianchi"]["conf_gol"]) == ("2", "media")
    # the sheet says 0 assists for Rossi in R2, TM says 1: totals 2 vs 1 -> lower value, media
    assert (r["Mario Rossi"]["assist"], r["Mario Rossi"]["conf_assist"]) == ("1", "media")
    audit = list(csv.DictReader(open(tmp_path / "audit_log.csv")))
    assert sum(a["kind"] == "coverage_manual" for a in audit) == 1
    assert sum(a["kind"] == "evidence_unmatched" for a in audit) == 9      # Extra0..8 are not TM players


def test_assists_not_reported_stay_single_source(tmp_path):
    _src(tmp_path, ss_lineup_m2=False)
    ev = _sheet(tmp_path, assists="")
    reconcile.run(tmp_path, config.load(), evidence=ev)
    r = _rows(tmp_path)
    assert r["Mario Rossi"]["conf_minuti"] == "media"
    assert (r["Mario Rossi"]["assist"], r["Mario Rossi"]["conf_assist"]) == ("2", "bassa")


def test_minute_gap_in_sheet_takes_lower(tmp_path):
    _src(tmp_path, ss_lineup_m2=False)
    ev = _sheet(tmp_path, bianchi_off="12' st")          # 57' vs TM 60'
    reconcile.run(tmp_path, config.load(), evidence=ev)
    r = _rows(tmp_path)
    assert (r["Luca Bianchi"]["minuti"], r["Luca Bianchi"]["conf_minuti"]) == ("127", "media")


def test_sheet_requires_source(tmp_path):
    p = tmp_path / "e.csv"
    p.write_text("round,date,home,away,team,player,started,sub_on,sub_off,red_card,goals,assists,source_type,source_url,retrieved,note\n"
                 "1,2026-09-01,A,B,A,X,1,,,,0,0,tabellino,,2026-10-19,\n")
    with pytest.raises(E.EvidenceError):
        E.read_sheets(p)
