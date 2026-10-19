from aboringbot.reconciler import identity as I


def test_norm_accents():
    assert I.norm("Nicolò  Bianchi") == "nicolo bianchi"


def test_middle_name():
    assert I.name_score("Orso Maria De Ponti", "Orso De Ponti") >= 0.9


def test_match_players_dob_breaks_tie():
    L = {"1": dict(name="Nicolò Bianchi", dob="2008-01-02"), "2": dict(name="Luca Bianchi", dob="1999-05-05")}
    R = {"a": dict(name="Nicolo Bianchi", dob="2008-01-02"), "b": dict(name="L. Bianchi", dob="1999-05-05")}
    got, ul, ur = I.match_players(L, R)
    m = {l: r for l, r, *_ in got}
    assert m["1"] == "a"


def test_clubs():
    m = I.match_clubs({"1": "USD Castellanzese 1921", "2": "Oltrepò FBC"}, {"x": "Oltrepò FBC", "y": "Castellanzese"})
    assert m["1"][0] == "y" and m["2"][0] == "x"
