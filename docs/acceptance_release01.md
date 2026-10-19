# Acceptance test: agent vs Release 01 (run 19 Oct 2026, second run with manual match sheets)

Cutoff: rounds 1-7 of girone D (includes the round-5 match played on 14/10; round 8 excluded).
Sources: Transfermarkt (62 match reports), SofaScore (62 matches, 57 with lineups) and, for the 5 matches
without SofaScore lineups, manual match sheets from public match reports (`data/manual/evidence.csv`).
Universe: the 40 players of the Release 01 reconciled file. Identity matching: 40/40.

**Result: 9/10 Release 01 picks reproduced under the strict method** (first run today: 5/10).
Not reproduced: Tirapelle enters (60.8), Arpini drops out (60.7, 9th overall, FB quota of 2 already filled).
Scores: 4 of 10 identical (Valmori 94.4, Citterio 75.6, Matella 59.8, Sassaro 57.7); the other picks differ
because the eligible pool differs (percentiles are computed within role group, see below).

## The 5 matches without SofaScore lineups and the sheets used

Selection rule (fixed before reading the values): one primary sheet per match; the official report of
either club if it has a complete tabellino with substitution minutes for both teams; otherwise the local-press
tabellino carried by more outlets. Other reports are used only for fields the primary does not give, and are
named in the row note. Retrieval date 19/10/2026 for every row.

| match | primary sheet | other reports used |
|---|---|---|
| R1 Pavia-Crema 0-0 (06/09) | calciopavia1911.it, official match report | - |
| R2 Solbiatese-Casatese Merate 0-0 (12/09) | varesenews.it tabellino (same text on varesenoi.it); no club report has minutes | varesesport.com cronaca: Montesano red card at 7' st |
| R5 Pavia-Arconatese 1-1 (27/09) | gsarconatese.it, official (the Pavia report omits Lucino->Lecchi) | calciopavia1911.it cronaca: assist Odalo on Raballo's goal |
| R6 Arconatese-Pro Sesto 1-1 (04/10) | gsarconatese.it, official | - |
| R7 Pistoiese-Correggese 1-0 (11/10) | correggese.it, official | reportpistoia.com cronaca: Motti's goal had no assist |

Assists: reported for R1, R2, R7 (no assisted goals), R5 Pavia (Odalo). Not reported (blank in the file, the
match stays single-source for assists) for R5 Arconatese and R6 both teams: no source names an assist.
159 rows, 158 matched automatically to Transfermarkt players; "Saporetti" (R7) was ambiguous between two
Pistoiese players and was written as Simone Saporetti by hand, with the reason in the note.
Sheet vs Transfermarkt per match: 0-2' differences on substitution minutes (e.g. Tavanti R7 71' vs 73'),
no conflict on starters, substitutes or goals.

## Per-field match rate (strict method)

| field | match | first run | note |
|---|---|---|---|
| nato, club, pos_classifica, partite_squadra, gs_squadra | 40/40 | 40/40 | |
| presenze, titolari, gol | 40/40 | 40/40 | |
| ruolo | 39/40 | 39/40 | Giorgi, see (a) |
| minuti | 28/40 | 29/40 | Tavanti now 502 (sheet 71' in R7) vs 503 |
| assist | 34/40 | 34/40 | |
| conf_minuti | 33/40 | 11/40 | the 26 "bassa" from missing lineups are gone |
| conf_gol | 32/40 | 32/40 | all 8 are "alta" (reference) vs "media" |
| conf_assist | 39/40 | 38/40 | Odalo now "media" (assist confirmed by the Pavia report) |

Gate-level agreement (bassa or not on all key fields): 36/40 (first run: 14/40).

## Picks (score.py unchanged)

| reference (= release_01.json) | agent, strict method |
|---|---|
| Valmori 94.4 | Valmori 94.4 |
| Lagomarsino 87.0 | Lagomarsino 81.9 |
| Citterio 75.6 | Citterio 75.6 |
| Latini 68.8 | Latini 73.6 |
| De Ponti 67.7 | De Ponti 72.8 |
| Arpini 65.6 | Itraloni 62.9 |
| Itraloni 61.8 | Diana 61.3 |
| Matella 59.8 | **Tirapelle 60.8** |
| Sassaro 57.7 | Matella 59.8 |
| Diana 55.6 | Sassaro 57.7 |

Why scores move: in the agent data Tirapelle (FB), Suatoni and Occhipinti (MID) pass the confidence gate,
so the FB and MID groups have more eligible players and the percentiles change (Lagomarsino, Latini,
De Ponti, Itraloni, Arpini); Diana has 3 assists instead of 2.
Diagnostic run (`--coverage common`, not the method): 8/10 (Viscardi and Tirapelle in, Arpini and Diana out).

## Every remaining difference, classified

(a) Release 01 likely errata: the automated sources (and club/press reports where available) agree against
the value used in Release 01, which came from zerozero (ZZ) or from TM = ZZ.

- Occhipinti minuti: 495 (ZZ, "bassa") vs 530 (TM 530, SofaScore 531) -> "media".
- Suatoni minuti: 506 (ZZ, "bassa") vs 482 (TM 482 = SofaScore 414 + R2 tabellino 68') -> "media".
- Grandinetti minuti: 247 (ZZ) vs 264 (TM 264, SofaScore 265).
- Serraglia minuti: 376 (ZZ) vs 377 (TM 377, SofaScore + sheets 378).
- Diana assist: 2 (ZZ) vs 3 (TM 3 = SofaScore 3).
- Geddo assist: 0 (ZZ) vs 1 (TM 1 = SofaScore 1).
- Lecchi minuti: 497 (TM = ZZ) vs 469: R3 Pavia-Solbiatese, TM 90' vs SofaScore 62'; the VareseSport
  tabellino has Lecchi off at 17' st (62'), so SofaScore is right and Release 01 took a wrong value.
- Giorgi ruolo: ATT vs MID. The method uses the Transfermarkt main position; it was already "Centrocampista"
  in the 18/10 squad snapshot (`radar_seried/raw/tm_squads_raw.csv`). No effect: Giorgi fails the 35% minutes gate.

(b) Source gap or source difference (neither Release 01 nor the agent is wrong under the rule):

- Tirapelle conf_minuti: "bassa" in Release 01 (zerozero mixed him with a namesake, minutes not checkable)
  vs "media" now (TM 626 = SofaScore + the two Arconatese official tabellini). Release 01 applied the rule
  correctly with the sources it had. **This is the only pick difference** (Tirapelle 60.8 in, Arpini 60.7 out).
- SofaScore substitution minutes 1-3' off TM, lower value taken (rule): Lagomarsino 602 vs 604, Viscardi 477
  vs 481, Randisi 379 vs 386, Giorgi 157 vs 160, Opoola 240 vs 244, Tavanti 502 vs 503 (R4 SofaScore 86' vs
  TM 85'; R7 Correggese report 26' st vs TM 73'; other press 28' st and 74').
- Mori minuti 478 vs 520, "bassa" in both: R5 Tropical Coriano-Pontedera SofaScore 46' vs TM 90'. The
  tuttocalciotoscana.com tabellino has Mori playing the full match, so 520 is right; the agent cannot use a
  sheet for a match SofaScore does cover (not supported yet).
- Assists, TM one more than SofaScore (rule -> lower, or "bassa" if the gap is 2): Viscardi 2 vs 3 (and his
  R6 assist is not reported by any tabellino), Giorgi 0 vs 1, Bianchi 1 vs 2, Grandinetti 0 vs 1 ("bassa": TM 2, SofaScore 0).
- conf_gol "alta" for 8 players and conf_minuti "alta" for 4 (Valmori, Bianchi, Matella, De Ponti) in
  Release 01 vs "media": "alta" needs an official report for the whole total; no total-level report entered.

(c) Agent bug: none confirmed. One open point, not changed:

- A per-match value of 0 known from one source only does not make the total single-source (the
  `part` logic in `reconcile.py`, unchanged from the first run). This matters for assists in R5 (Arconatese)
  and R6 (both teams), where no tabellino names an assist: Tirapelle (FB, assist gate) and Meriggi keep "media".
  With the stricter reading (any single-source match makes the total "bassa"), simulated by hand: Tirapelle
  drops and the 10 names are the Release 01 names (scores still differ). This is a reading of method sec. 1
  and needs an owner decision; the code was not changed.

Release 01 picks and the published rules are unchanged. Draft errata (not published):
`/workspace/radar_seried/errata_draft_20261019.md`.

## Reproduce

```bash
python -m aboringbot.cli reconcile --max-round 7 --universe REF.csv          # reads data/manual/evidence.csv
python -m aboringbot.cli accept --max-round 7 --reference REF.csv --score score.py --release release_01.json
```
