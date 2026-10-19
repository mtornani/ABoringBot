# Manual evidence

`evidence.csv`: match sheets read by a human from public match reports, for matches where an automated
source has no lineup. Format and rules are in `aboringbot/reconciler/evidence.py` (module docstring).

- One row per player who took part; a team listed for a match is a complete sheet.
- Minutes as written in the source (`66'`, `35' st`, `11' pt`); converted with the collectors' convention.
- `assists` blank = the source does not say (the match stays single-source for assists).
- Every row carries `source_url` and `retrieved` (YYYY-MM-DD). Names are written as in the source;
  any hand correction is explained in `note`.
- No data from sites that block automated access (zerozero, tuttocampo, Calciotel, seried.it).

Current content (19/10/2026): the 5 girone D matches up to round 7 without SofaScore lineups
(R1 Pavia-Crema, R2 Solbiatese-Casatese Merate, R5 Pavia-Arconatese, R6 Arconatese-Pro Sesto,
R7 Pistoiese-Correggese). See `docs/acceptance_release01.md` for the selection rule.
