# Player Role V2 — B41B Historical Cohort / Leakage Audit

- Development cohort rows: **85,740**
- Development seasons: **2019–2024**
- 2025 holdout opened: **No**
- Historical projection features used: **No**
- Model fit performed: **No**
- Predictor-target association computed: **No**
- Role weights derived: **No**
- Role thresholds derived: **No**
- Production change authorized: **No**

## Row counts by position

- DB: 21,386
- DL: 15,565
- K: 2,175
- LB: 15,984
- QB: 3,154
- RB: 8,479
- TE: 7,060
- WR: 11,937

## Leakage firewall

- Every feature window ends at or before its origin week.
- Every target window begins strictly after its origin week.
- No fantasy owner, roster ID, dynasty team, or username is present.
- The 2025 holdout is not downloaded or read by B41B.
- Historical Sleeper/FantasyPros projections remain excluded.

## Target handling

B41B stores raw future game components only. It deliberately does **not** convert those outcomes into the league-scored target yet. The exact scorer must be frozen before any model fitting.

Development cohort SHA256: `057454b904093b5f9e4a571d8a1e6c489289829ed07427dc79fcbe4ee4e424f4`
Builder SHA256: `84dcee287a9884976344acb13b844267105da0396fd4c1f02898b7d70c5d15dc`
