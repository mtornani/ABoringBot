from bs4 import BeautifulSoup
from aboringbot.collector.transfermarkt import sprite_minute, parse_report


def span(style, text=""):
    return BeautifulSoup(f'<span class="sb-sprite-uhr-klein" style="{style}">{text}</span>', "lxml").span


def test_sprite():
    assert sprite_minute(span("background-position: -144px -0px;")) == 5
    assert sprite_minute(span("background-position: -288px -36px;")) == 19
    assert sprite_minute(span("background-position: -252px -180px;")) == 58
    assert sprite_minute(span("background-position: -0px -433px;")) is None


REPORT = """
<div class="sb-heim"><a href="/a/startseite/verein/1/saison_id/2026">A</a></div>
<div class="sb-gast"><a href="/b/startseite/verein/2/saison_id/2026">B</a></div>
<div class="large-6 columns aufstellung-box"><a href="/a/startseite/verein/1">A</a>
 <div class="formation-player-container"><a href="/p/profil/spieler/10">P10</a></div></div>
<div class="large-6 columns"><a href="/b/startseite/verein/2">B</a>
 <div class="formation-player-container"><a href="/q/profil/spieler/20">Q20</a></div></div>
<div id="sb-tore"><ul><li class="sb-aktion-heim"><div class="sb-aktion-aktion">
 <a href="/p/leistungsdatendetails/spieler/10">P10</a>, Destro<br/>Assist: <a href="/r/leistungsdatendetails/spieler/11">R11</a></div></li></ul></div>
<div id="sb-wechsel"><ul><li class="sb-aktion-heim">
 <span class="sb-sprite-uhr-klein" style="background-position: -252px -180px;"></span>
 <div class="sb-aktion-aktion"><span class="sb-aktion-wechsel-ein"><a href="/r/leistungsdatendetails/spieler/11">R11</a></span>
 <span class="sb-aktion-wechsel-aus"><a href="/p/leistungsdatendetails/spieler/10">P10</a></span></div></li></ul></div>
"""


def test_report_minutes_goals_assists():
    apps, names, notes = parse_report(REPORT, dict(id=1, home=1, away=2))
    a = {x["player"]: x for x in apps}
    assert a[10]["minutes"] == 58 and a[10]["goals"] == 1 and a[10]["started"]
    assert a[11]["minutes"] == 32 and a[11]["assists"] == 1 and not a[11]["started"]
    assert a[20]["minutes"] == 90
