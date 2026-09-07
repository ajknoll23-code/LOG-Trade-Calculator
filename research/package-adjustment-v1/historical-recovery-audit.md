# Historical Package-Trade Recovery Audit

**Status: RESEARCH ONLY — no production consumer changed.**

## Result

**0 of 15 existing 2026 current-league trades can be legitimately recovered as pre-trade numeric observations.**

The existing trades occurred from **2026-04-24 through 2026-05-27**.

The earliest repository commit available is **2026-08-13**, and the first frozen model-history snapshot is **2026-08-31**. Therefore every existing trade predates every available committed calculator/model state.

## Recovery sources checked

| Source | Earliest available state | Recoverable trades |
|---|---:|---:|
| Git repository history | 2026-08-13 03:38:56 UTC | 0 |
| Frozen model-history snapshots | 2026-08-31 20:49:26 UTC | 0 |

## Methodology decision

Current, August, or September values must **not** be substituted for April-May pre-trade values. Doing that would introduce hindsight leakage.

The 15 existing trades may still be used for:

- package-shape counts;
- asset-count distributions;
- player-only versus pick-involving trade structure;
- qualitative examples.

They may **not** be used to fit or validate Package Adjustment lambda because there is no contemporaneous pre-trade model state.

## Forward-looking status

Prospective evidence capture is already active. Every future completed trade can become numerically eligible when a stored snapshot exists strictly before the Sleeper transaction timestamp.

Package Preference Voting remains a supplemental calibration source rather than the sole path to promotion.
