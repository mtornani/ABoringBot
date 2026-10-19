"""Conflict rule of metodo.md sec. 1, applied exactly as written (fixed in advance).

- 2 sources agree                                  -> value, confidence "media"
  ("alta" needs an official match report or club/press report agreeing; not automated yet)
- gap of 1 on goals/assists, or <= 30' on minutes  -> LOWER value, confidence "media"
- larger gap                                       -> "bassa" until a match report settles it
  (value kept = lower one, as in the Release 01 file)
- one source only                                  -> that value, "bassa"
- no source                                        -> 0, "bassa"

Internal status labels: confirmed / confirmed_lower / doubtful / missing.
"""

CONF = {"confirmed": "media", "confirmed_lower": "media", "doubtful": "bassa", "missing": "bassa"}


def apply(field, a, b, max_gap_ga=1, max_gap_min=30):
    """Return (value, status, confidence, gap)."""
    vals = [v for v in (a, b) if v is not None]
    if not vals:
        return 0, "missing", "bassa", None
    if len(vals) == 1:
        return vals[0], "missing", "bassa", None
    gap = abs(a - b)
    if gap == 0:
        st = "confirmed"
    else:
        limit = max_gap_min if field == "minuti" else max_gap_ga
        st = "confirmed_lower" if gap <= limit else "doubtful"
    return min(a, b), st, CONF[st], gap
