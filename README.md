# ABoringBot

A set of AI agents that collect public football data, confirm every key number on two independent sources, score players with a fixed method written down before ranking, and write a sourced justification for each pick.

Scope: lower leagues, Serie D / Lega Pro and below, where data is thin and few people check it.

## Why "boring"

- **Boring as in drilling.** Digging where few people look: lower-league fixtures, match reports, federation releases, local press.
- **Boring as in unglamorous.** Most of the work is verification: matching minutes across sources, resolving conflicts, logging what was checked. The system is built to do that work every time, not to be interesting.

Agents replace hand-maintained scraping scripts. Agents collect and check data; a fixed, pre-registered method decides.

## Principles

1. **Public sources only.** Every number must be traceable to a public page: league releases, match reports, club sites, local press, public databases.
2. **Two-source rule.** Key figures (minutes, goals, assists) must be confirmed by two independent sources. Conflicts are resolved with a rule set in advance: small gaps take the lower value at reduced confidence; larger gaps exclude the figure until an official match report settles it.
3. **Method frozen before ranking.** Weights, gates and parameters are written and dated before any ranking is computed. Any change creates a new dated version and applies only to later picks.
4. **Every pick logged and graded, misses included.** Picks are frozen in a public log with date, method version, score, inputs and sources. Entries are never edited; corrections are appended. Results at each checkpoint are published, failures included, against a naive baseline.
5. **A human signs before anything ships.** No output is published without review and sign-off by the owner.

## Live now: the Radar

The first output produced under these rules is the monthly Radar.

- Italian: https://www.matchanalysispro.online/radar/
- English: https://www.matchanalysispro.online/en/radar/

**Release 01**, 18 Oct 2026: 10 under-23 picks from Serie D, girone D. Data was collected and reconciled with heavy manual supervision; the agent pipeline below is not yet running.

### Method v1.0 (fixed 18 Oct 2026, before the first release)

**Gates** (all required):

- born 2003 or later;
- at least 35% of available minutes (team matches x 90);
- key figures confirmed by two sources (minutes for all roles; plus goals and assists for forwards; plus assists for full-backs).

**Weights** (composite score 0-100):

| Component | Weight | Definition |
|---|---|---|
| Role output | 0.45 | role-specific, see below |
| Minutes share | 0.25 | minutes / available minutes |
| Age vs under quota | 0.15 | 1.0 for born 2003-2005, 0.6 for 2006-2008 (players a team must field under the under rule) |
| Team position | 0.15 | (19 - league position) / 18 |

**Role output** (per-90 values shrunk toward a declared role mean with a 270-minute prior):

- FW: (G+A)/90.
- MID: mean of percentiles of (G+A)/90 and starts share.
- FB/WB: 0.6 x percentile of A/90 + 0.4 x percentile of starts share.
- CB: 0.5 x percentile of starts share + 0.5 x percentile of team goals conceded per match (inverted). This is a team figure, not on-pitch goals against, which is not public. Stated as a known limitation.

**Percentiles within role.** Each component becomes a percentile among eligible players of the same role group. Scores compare a player with his group, not across roles. Small groups make percentiles coarse.

**Role quotas** for the 10 picks: 2 CB, 2 FB, 3 MID, 3 FW. Unfilled slots go to the best remaining eligible players and are declared in the release. Ties: higher minutes share, then alphabetical.

**Validation checkpoints** (pre-registered): ~24 Nov 2026 (after 6 rounds), ~31 Jan 2027 (after 15 rounds), 3 May 2027 (end of season). A pick counts as a success if at season end it keeps its minutes share (-10 pp tolerance) and has role output above the group median, or moves up a level or is called up to a representative or youth national team. The success rate is published over all picks, compared against a naive baseline: the three under players with the most minutes in the group.

**Justification template**: three lines per pick, each with a number and a source: usage, output, context.

## Building: agent pipeline

Status: **in design**. Nothing below is implemented yet.

```mermaid
flowchart TD
    S[Public sources] --> C[Collector]
    C --> R[Reconciler]
    R --> SC[Scorer]
    SC --> E[Explainer]
    E --> A[Auditor]
    A --> H[Human sign-off]
    H --> P[Release + public log]
    R -. low confidence .-> Q[Hold: under observation]
```

| Agent | Role (design) |
|---|---|
| Collector | Fetches fixtures, match reports, appearances and standings from public sources; stores raw values per source with URL and retrieval time. |
| Reconciler | Matches player identities across sources, compares fields, applies the pre-set conflict rule, assigns confidence (high / medium / low). |
| Scorer | Runs the frozen method version on reconciled data. No discretion: same input, same output. |
| Explainer | Writes the three-line justification for each pick, each line citing a number and its source. |
| Auditor | Re-checks every cited number against its source, checks gates and quotas, flags anything that does not trace back. |

Agents do not change weights, gates or quotas. Method changes are made by a human, dated, and versioned.

## Repository status

Early. This repository does not yet contain the pipeline described above.

- It contains an earlier scaffold from the project's previous phase (Cloudflare Worker + D1 schema,). It is not part of the Radar workflow and may be replaced.
- The v1.0 method and scoring script used for Release 01 are maintained outside this repository for now.

## Owner

Mirko Tornani, San Marino. Former youth coach (15 years), UEFA B and C licences, scout.

## License

License: TBD
