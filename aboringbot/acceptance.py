"""Acceptance test: agent CSV vs manually reconciled reference CSV, then score.py on both."""
import csv, json, subprocess, sys
from pathlib import Path

from .reconciler.identity import name_score, norm

FIELDS = ["nato", "ruolo", "club", "pos_classifica", "partite_squadra", "presenze", "titolari", "minuti", "gol",
          "assist", "conf_minuti", "conf_gol", "conf_assist", "gs_squadra"]
GATE = {"conf_minuti", "conf_gol", "conf_assist"}


def _score(script, csv_path):
    r = subprocess.run([sys.executable, str(script), str(csv_path), "--json"], capture_output=True, text=True,
                       cwd=Path(script).parent)
    if r.returncode:
        raise RuntimeError(r.stderr)
    return json.loads(r.stdout)


def cause(field, ref, agent, audit_rows):
    a = [x for x in audit_rows if x.get("field") == field.replace("conf_", "")]
    if field in GATE:
        if ref == "alta" and agent == "media":
            return "alta needs an official match/club report as one of the two sources; not automated"
        if agent == "bassa" and ref in ("alta", "media"):
            src = a[0] if a else {}
            if src.get("status") == "missing":
                return "only one automated source has the figure (second source missing)"
            if src.get("status") == "partial":
                return (f"second source has no lineup for {src.get('per_match','').count('no-lineup')} of his matches "
                        f"(TM total {src.get('tm')} of which {src.get('tm_only_part')} single-source; SofaScore {src.get('ss')}): part of the figure is single-source")
            return f"automated sources disagree beyond the rule threshold (tm {src.get('tm')}, ss {src.get('ss')}); reference used a third source"
        if ref == "bassa" and agent != "bassa":
            return "reference had a conflict with zerozero/TM; TM and SofaScore agree (within rule) at this cutoff"
    if a:
        x = a[0]
        return f"tm {x.get('tm')} / ss {x.get('ss')} -> {x.get('status')} -> {x.get('decision')}; per match: {x.get('per_match') or '-'}"
    if field in ("pos_classifica", "partite_squadra", "gs_squadra"):
        return "team figure computed from match results at cutoff differs from reference"
    if field == "ruolo":
        return "Transfermarkt main position maps to a different role group than the one used in the reference"
    return "both automated sources agree on a value different from the reference (reference used another source or cutoff)"


def run(out, reference, score, release=None):
    out = Path(out)
    agent = list(csv.DictReader(open(out / "reconciled.csv")))
    ref = list(csv.DictReader(open(reference)))
    audit = list(csv.DictReader(open(out / "audit_log.csv")))
    lines = ["# Acceptance test vs Release 01 reference", "",
             f"Agent output: `{out / 'reconciled.csv'}`; reference: `{reference}`", ""]
    pairs, missing = [], []
    for r in ref:
        best = max(agent, key=lambda x: name_score(x["nome"], r["nome"]) + (0.2 if norm(x["club"]) == norm(r["club"]) else 0), default=None)
        if best and name_score(best["nome"], r["nome"]) >= 0.85:
            pairs.append((r, best))
        else:
            missing.append(r["nome"])
    lines += [f"Reference rows: {len(ref)}; matched in agent output: {len(pairs)}; missing: {missing or 'none'}", "",
              "## Match rate per field", "", "| field | exact match | rate |", "|---|---|---|"]
    mism = []
    rates = {}
    for f in FIELDS:
        ok = 0
        for r, a in pairs:
            rv, av = r[f], a[f]
            if f == "club":
                same = norm(rv) == norm(av)
            else:
                same = rv == av
            if same:
                ok += 1
            else:
                rows = [x for x in audit if norm(x.get("player", "")) == norm(a["nome"])]
                mism.append((r["nome"], f, rv, av, cause(f, rv, av, rows)))
        rates[f] = ok / max(1, len(pairs))
        lines.append(f"| {f} | {ok}/{len(pairs)} | {rates[f]:.0%} |")
    gate_ok = sum(1 for r, a in pairs if all((r[g] == "bassa") == (a[g] == "bassa") for g in GATE))
    lines += ["", f"Gate-level agreement (bassa vs not bassa on all three conf fields): {gate_ok}/{len(pairs)}", ""]
    lines += ["## Mismatches", "", "| player | field | reference | agent | cause |", "|---|---|---|---|---|"]
    lines += [f"| {n} | {f} | {rv} | {av} | {c} |" for n, f, rv, av, c in mism]
    ra = _score(score, out / "reconciled.csv")
    rr = _score(score, reference)
    rel = json.load(open(release)) if release else None
    lines += ["", "## score.py on agent output vs reference", ""]
    def picks(x): return [(p["nome"], p["ruolo"], p["score"]) for p in x["scelti"]]
    pa, pr = picks(ra), picks(rr)
    lines += ["| # | reference pick | ref score | agent pick | agent score |", "|---|---|---|---|---|"]
    for i in range(max(len(pa), len(pr))):
        a_ = pa[i] if i < len(pa) else ("-", "", "")
        r_ = pr[i] if i < len(pr) else ("-", "", "")
        lines.append(f"| {i+1} | {r_[0]} ({r_[1]}) | {r_[2]} | {a_[0]} ({a_[1]}) | {a_[2]} |")
    same_set = {norm(x[0]) for x in pa} == {norm(x[0]) for x in pr}
    same_scores = sorted((norm(x[0]), x[2]) for x in pa) == sorted((norm(x[0]), x[2]) for x in pr)
    rel_ok = None
    if rel:
        rp = sorted((norm(p["name"]), p["score"]) for p in rel["picks"])
        rel_ok = dict(names=sorted(x[0] for x in rp) == sorted(norm(x[0]) for x in pa),
                      scores=rp == sorted((norm(x[0]), x[2]) for x in pa))
    lines += ["", f"Same 10 names as reference: {same_set}; same names and scores: {same_scores}",
              f"vs release_01.json: {rel_ok}", "", "Agent quota notes: " + ("; ".join(ra["note"]) or "none")]
    rep = "\n".join(lines) + "\n"
    (out / "acceptance_report.md").write_text(rep)
    (out / "acceptance.json").write_text(json.dumps(dict(rates=rates, mismatches=mism, picks_agent=pa, picks_ref=pr,
                                                         same_set=same_set, same_scores=same_scores, release=rel_ok,
                                                         missing=missing), ensure_ascii=False, indent=1))
    print(rep)
    return rates
