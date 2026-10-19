# Acceptance test: agent vs Release 01 (run 19 Oct 2026)

Cutoff: rounds 1-7 of girone D (includes the round-5 match played on 14/10; round 8 excluded).
Sources: Transfermarkt (62 match reports) and SofaScore (62 matches, 57 with lineups).
Universe: the 40 players of the Release 01 reconciled file. Identity matching: 40/40.

## Per-field match rate (strict method)

| field | match | note |
|---|---|---|
| nato, club, pos_classifica, partite_squadra, gs_squadra | 40/40 | |
| presenze, titolari, gol | 40/40 | |
| ruolo | 39/40 | Giorgi: Transfermarkt main position today is "Centrocampista" (MID); reference ATT |
| minuti | 29/40 | see below |
| assist | 34/40 | see below |
| conf_minuti | 11/40 | 26 players "bassa" because a match has no SofaScore lineup; 4 "alta" in reference vs "media" (no automated match-report source) |
| conf_gol | 32/40 | all 8 are "alta" (reference, club match reports) vs "media"; no gate effect |
| conf_assist | 38/40 | Grandinetti (TM 2, SofaScore 0 -> bassa), Odalo (his only assist is in a match without SofaScore lineup) |

Gate-level agreement (bassa or not on all key fields): 14/40 strict, 35/40 diagnostic.

## Minutes and assists mismatches, with cause

- Lower-value rule on small gaps: SofaScore records substitutions 1-3 minutes apart from Transfermarkt, so the rule takes the lower total where the reference had TM = zerozero exactly: Lagomarsino 602 vs 604, Viscardi 477 vs 481, Randisi 379 vs 386, Giorgi 157 vs 160, Opoola 240 vs 244.
- Real disagreements between sources: Lecchi (one match TM 90', SofaScore 62') 469 vs 497; Mori (one match TM 90', SofaScore 46') 478 vs 520, "bassa" in both.
- Reference took the zerozero value, both automated sources agree on another: Grandinetti 264 vs 247, Suatoni 482 vs 506, Occhipinti 530 vs 495, Serraglia 377 vs 376.
- Assists: TM counts one more than SofaScore for Viscardi, Giorgi, Bianchi, Grandinetti, Odalo (rule -> lower or bassa); Diana 3 and Geddo 1 in both automated sources vs 2 and 0 in the reference (zerozero value).

## Picks (score.py unchanged)

| reference (= release_01.json) | agent, strict method | agent, diagnostic |
|---|---|---|
| Valmori 94.4 | Valmori 96.2 | Valmori 94.2 |
| Lagomarsino 87.0 | Latini 72.1 | Lagomarsino 81.9 |
| Citterio 75.6 | De Ponti 69.6 | Latini 73.6 |
| Latini 68.8 | Matella 60.6 | Viscardi 73.3 |
| De Ponti 67.7 | Sassaro 46.9 | Citterio 73.1 |
| Arpini 65.6 | Bita 42.5 | De Ponti 72.8 |
| Itraloni 61.8 | Occhipinti 40.8 | Itraloni 62.9 |
| Matella 59.8 | Bianchi 27.5 | Tirapelle 60.8 |
| Sassaro 57.7 | Randisi 26.2 | Matella 59.8 |
| Diana 55.6 | Grandinetti 17.5 | Sassaro 57.7 |

- Strict: 5/10 names in common, no FB eligible, scores differ. Not reproduced.
- Diagnostic (`--coverage common`: confidence judged on the matches both sources cover; **not the method**): 8/10 names in common. Differences: Viscardi enters (reference excluded him on assists with one source), Tirapelle enters (reference had a zerozero minutes conflict); Arpini and Diana drop out.

To reproduce Release 01 under the method, the 5 matches without SofaScore lineups need a second source (match reports entered in `data/manual/evidence.csv`, or zerozero when reachable).
