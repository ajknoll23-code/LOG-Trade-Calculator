# Historical PROD_MULT Lineage Trace

## Verdict

Input drift is not the main explanation. Even against release-era source snapshots, the legacy generator remains materially different from the frozen production table. The next step should focus on recovering the actual historical formula/manual transformation that produced PROD_MULT_DATA.

## Frozen baseline origin

- Frozen entries: **823**
- Recorded `index.html` SHA256: `eaba01a62f67d2ca40b70f975127b057da86068cf1ff91495b687afc9e32b8b4`
- Git commits whose `index.html` exactly matches that SHA256: **11**
  - `4c55004955c8` — 2026-08-28T16:02:12-07:00 — Add files via upload
  - `8ae42e49715c` — 2026-08-28T16:01:42-07:00 — Add files via upload
  - `352928eca275` — 2026-08-28T16:01:23-07:00 — Add files via upload
  - `3678a3a6ddf0` — 2026-08-28T22:51:27Z — Sync Sleeper data (2026-08-28 22:51 UTC)
  - `869f26014af2` — 2026-08-28T15:34:24-07:00 — Add files via upload

## Release-manifest snapshot recovery

- Source snapshots recorded: **8**
- Code snapshots recorded: **5**
- Commits matching every source snapshot simultaneously: **265**
- Commits matching every code snapshot simultaneously: **89**
- Commits matching the full source + code lineage simultaneously: **89**
- Commits matching all four inputs used by the legacy PROD_MULT formula: **388**

## Historical replay anchor

- Commit: `4c55004955c8746fbb6a84cbb20afafff8ad86d6`
- Date: 2026-08-28T16:02:12-07:00
- Subject: Add files via upload

## Replay using current committed inputs

- Status: **PASS**
- Pipeline code: `current_archived_reconstruction`
- History code: `current_canonical`
- PPG/aliases code: `current_canonical`
- Generated players: **1125**
- Compared overlap rows: **695**
- Exact matches to frozen baseline: **58**
- Median absolute drift: **0.0339**
- P90 absolute drift: **0.1328**
- P95 absolute drift: **0.1806**
- Maximum absolute drift: **0.3399**

Largest drifts:

| Player | Pos | Frozen | Replayed | Diff | Projection source |
|---|---|---:|---:|---:|---|
| jonathan greenard | DL | 0.3460 | 0.6859 | +0.3399 | blend_50_50 |
| jeremiyah love | RB | 1.0630 | 0.7362 | -0.3268 | blend_50_50 |
| poona ford | DL | 0.6380 | 0.3346 | -0.3034 | sleeper_only |
| kayvon thibodeaux | DL | 0.2180 | 0.5099 | +0.2919 | blend_50_50 |
| brian burns | LB | 1.0560 | 0.7659 | -0.2901 | blend_50_50 |
| dru phillips | DB | 0.6750 | 0.3951 | -0.2799 | sleeper_only |
| devonte wyatt | DL | 0.3070 | 0.5661 | +0.2591 | sleeper_only |
| will anderson | LB | 0.9090 | 0.6500 | -0.2590 | sleeper_only |
| milton williams | DL | 0.3650 | 0.6238 | +0.2588 | sleeper_only |
| marquise brown | WR | 0.5020 | 0.2550 | -0.2470 | sleeper_only |
| byron young | LB | 0.8660 | 0.6197 | -0.2463 | blend_50_50 |
| tj watt | LB | 0.8980 | 0.6534 | -0.2446 | blend_50_50 |
| nik bonitto | LB | 0.8140 | 0.5783 | -0.2357 | blend_50_50 |
| kayden mcdonald | DL | 0.1500 | 0.3772 | +0.2272 | sleeper_only |
| dallas turner | LB | 0.7540 | 0.5297 | -0.2243 | blend_50_50 |

## Replay using recovered release-era inputs

- Status: **PASS**
- Pipeline code: `historical_commit`
- History code: `historical_commit`
- PPG/aliases code: `historical_commit`
- Generated players: **1125**
- Compared overlap rows: **695**
- Exact matches to frozen baseline: **58**
- Median absolute drift: **0.0339**
- P90 absolute drift: **0.1328**
- P95 absolute drift: **0.1806**
- Maximum absolute drift: **0.3399**

Largest drifts:

| Player | Pos | Frozen | Replayed | Diff | Projection source |
|---|---|---:|---:|---:|---|
| jonathan greenard | DL | 0.3460 | 0.6859 | +0.3399 | blend_50_50 |
| jeremiyah love | RB | 1.0630 | 0.7362 | -0.3268 | blend_50_50 |
| poona ford | DL | 0.6380 | 0.3346 | -0.3034 | sleeper_only |
| kayvon thibodeaux | DL | 0.2180 | 0.5099 | +0.2919 | blend_50_50 |
| brian burns | LB | 1.0560 | 0.7659 | -0.2901 | blend_50_50 |
| dru phillips | DB | 0.6750 | 0.3951 | -0.2799 | sleeper_only |
| devonte wyatt | DL | 0.3070 | 0.5661 | +0.2591 | sleeper_only |
| will anderson | LB | 0.9090 | 0.6500 | -0.2590 | sleeper_only |
| milton williams | DL | 0.3650 | 0.6238 | +0.2588 | sleeper_only |
| marquise brown | WR | 0.5020 | 0.2550 | -0.2470 | sleeper_only |
| byron young | LB | 0.8660 | 0.6197 | -0.2463 | blend_50_50 |
| tj watt | LB | 0.8980 | 0.6534 | -0.2446 | blend_50_50 |
| nik bonitto | LB | 0.8140 | 0.5783 | -0.2357 | blend_50_50 |
| kayden mcdonald | DL | 0.1500 | 0.3772 | +0.2272 | sleeper_only |
| dallas turner | LB | 0.7540 | 0.5297 | -0.2243 | blend_50_50 |

## Best Git-history lineage matches

| Commit | Date | Index exact | Sources | Code | Formula inputs | Subject |
|---|---|---:|---:|---:|---:|---|
| `4c55004955c8` | 2026-08-28T16:02:12-07:00 | yes | 8/8 | 5/5 | 4/4 | Add files via upload |
| `8ae42e49715c` | 2026-08-28T16:01:42-07:00 | yes | 8/8 | 2/5 | 4/4 | Add files via upload |
| `352928eca275` | 2026-08-28T16:01:23-07:00 | yes | 8/8 | 2/5 | 4/4 | Add files via upload |
| `3678a3a6ddf0` | 2026-08-28T22:51:27Z | yes | 8/8 | 2/5 | 4/4 | Sync Sleeper data (2026-08-28 22:51 UTC) |
| `869f26014af2` | 2026-08-28T15:34:24-07:00 | yes | 8/8 | 2/5 | 4/4 | Add files via upload |
| `b124bf30325d` | 2026-08-28T15:34:05-07:00 | yes | 8/8 | 2/5 | 4/4 | Add files via upload |
| `80226dc682c8` | 2026-08-28T15:33:43-07:00 | yes | 8/8 | 2/5 | 4/4 | Add files via upload |
| `6aefdc1f2c78` | 2026-08-28T14:12:10-07:00 | yes | 8/8 | 2/5 | 4/4 | Add files via upload |
| `b7ac6dd7dee2` | 2026-08-28T14:11:16-07:00 | yes | 8/8 | 2/5 | 4/4 | Add files via upload |
| `fb2d0552500e` | 2026-08-28T14:10:42-07:00 | yes | 8/8 | 2/5 | 4/4 | Add files via upload |
| `42a58338ad09` | 2026-08-28T14:08:46-07:00 | yes | 8/8 | 0/5 | 4/4 | Add files via upload |
| `b35c8c8d033c` | 2026-08-28T22:41:13-07:00 | no | 8/8 | 5/5 | 4/4 | Rename scripts/idp_v1_model_delta_transport_candidate.json to research/idp-v1-development/idp_v1_model_delta_transport_candidate.json |
| `12bfe2a25c66` | 2026-08-28T22:40:48-07:00 | no | 8/8 | 5/5 | 4/4 | Rename scripts/idp_v1_live_anchored_report.md to research/idp-v1-development/idp_v1_live_anchored_report.md |
| `1bd3a6aae3a6` | 2026-08-28T22:40:28-07:00 | no | 8/8 | 5/5 | 4/4 | Rename scripts/idp_v1_live_anchored_candidate.py to research/idp-v1-development/idp_v1_live_anchored_candidate.py |
| `d40b593b3a4c` | 2026-08-28T22:40:10-07:00 | no | 8/8 | 5/5 | 4/4 | Rename scripts/idp_v1_live_anchored_candidate.json to research/idp-v1-development/idp_v1_live_anchored_candidate.json |

## Interpretation rule

- If the historical-input replay becomes nearly exact, the old audit overstated formula drift because mutable inputs had changed.
- If the historical-input replay remains materially different, the baked table came from a different formula, manual transformation, baseline choice, position mapping, or other unrecorded step.
- This audit does **not** change `index.html`, the frozen IDP V1 release, or any player value.

