"""ABoringBot command line.

  python -m aboringbot.cli collect   --max-round 7 [--date YYYY-MM-DD]
  python -m aboringbot.cli reconcile --max-round 7 [--date ...] [--universe ref.csv]
  python -m aboringbot.cli accept    --max-round 7 --reference ref.csv --score score.py --release release.json
  python -m aboringbot.cli run       (collect + reconcile)
"""
import argparse, json, sys, time
from datetime import date
from pathlib import Path

from . import config
from .fetch import Cache, Fetcher, BrowserFetcher

DATA = config.ROOT / "data"


def _paths(a):
    raw = DATA / "raw"
    out = DATA / "out" / a.date / f"round{a.max_round:02d}{getattr(a, 'out_suffix', '')}"
    out.mkdir(parents=True, exist_ok=True)
    return raw, out


def cmd_collect(a, cfg):
    from .collector import transfermarkt, sofascore
    raw, out = _paths(a)
    cache = Cache(raw, a.date)
    t0 = time.time()
    tm = Fetcher(cache, "transfermarkt", cfg["fetch"]["tm_delay_s"])
    d = transfermarkt.collect(tm, cfg, a.max_round)
    (out / "source_tm.json").write_text(json.dumps(d, ensure_ascii=False, indent=1))
    print(f"[tm] fetch stats {tm.stats}, {len(d['apps'])} appearances, {len(d['notes'])} notes")
    if not a.skip_sofascore:
        sf = BrowserFetcher(cache, "sofascore", cfg["fetch"]["sofascore_delay_s"])
        try:
            d = sofascore.collect(sf, cfg, a.max_round)
        finally:
            sf.close()
        (out / "source_sofascore.json").write_text(json.dumps(d, ensure_ascii=False, indent=1))
        print(f"[sofascore] fetch stats {sf.stats}, {len(d['notes'])} notes")
    print(f"collect done in {time.time()-t0:.0f}s -> {out}")


def cmd_reconcile(a, cfg):
    from .reconciler import reconcile
    raw, out = _paths(a)
    t0 = time.time()
    res = reconcile.run(out, cfg, universe=a.universe, coverage_mode=a.coverage, evidence=a.evidence)
    print(f"reconcile done in {time.time()-t0:.1f}s: {res}")


def cmd_accept(a, cfg):
    from . import acceptance
    raw, out = _paths(a)
    acceptance.run(out, a.reference, a.score, a.release)


def main(argv=None):
    p = argparse.ArgumentParser(prog="aboringbot")
    p.add_argument("command", choices=["collect", "reconcile", "accept", "run"])
    p.add_argument("--max-round", type=int, required=True, help="cutoff: last round included")
    p.add_argument("--date", default=date.today().isoformat(), help="run date (raw cache folder)")
    p.add_argument("--universe", help="restrict output to the players of this CSV (acceptance test)")
    p.add_argument("--reference"); p.add_argument("--score"); p.add_argument("--release")
    p.add_argument("--coverage", choices=["strict", "common"], default="strict",
                   help="strict (method): a figure partly covered by one source only is 'bassa'. "
                        "common (diagnostic only, not the method): confidence from the matches both sources cover")
    p.add_argument("--out-suffix", default="", help="write into round<NN><suffix> (e.g. for diagnostic runs)")
    p.add_argument("--evidence", default=str(DATA / "manual" / "evidence.csv"),
                   help="manual third-source CSV (match reports read by a human)")
    p.add_argument("--skip-sofascore", action="store_true")
    a = p.parse_args(argv)
    cfg = config.load()
    if a.command in ("collect", "run"):
        cmd_collect(a, cfg)
    if a.command in ("reconcile", "run"):
        cmd_reconcile(a, cfg)
    if a.command == "accept":
        cmd_accept(a, cfg)


if __name__ == "__main__":
    main()
