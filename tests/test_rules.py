from aboringbot.reconciler import rules


def test_agree():
    assert rules.apply("minuti", 555, 555) == (555, "confirmed", "media", 0)


def test_small_gap_minutes_takes_lower():
    assert rules.apply("minuti", 411, 437) == (411, "confirmed_lower", "media", 26)


def test_30_minutes_is_small():
    assert rules.apply("minuti", 600, 630)[1:3] == ("confirmed_lower", "media")


def test_large_gap_minutes():
    assert rules.apply("minuti", 572, 506) == (506, "doubtful", "bassa", 66)


def test_goal_gap_one_and_two():
    assert rules.apply("assist", 5, 4) == (4, "confirmed_lower", "media", 1)
    assert rules.apply("assist", 2, 0) == (0, "doubtful", "bassa", 2)


def test_single_source():
    assert rules.apply("gol", 3, None) == (3, "missing", "bassa", None)
    assert rules.apply("gol", None, None) == (0, "missing", "bassa", None)
