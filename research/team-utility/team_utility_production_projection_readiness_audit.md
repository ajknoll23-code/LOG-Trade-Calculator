# Team Utility Production Projection Readiness Audit

Research-only. **No production values or Team Utility constants were changed.**

## Candidate architecture

Use PLAYER_DB.proj2026 to select starters; Fundamental Value remains the Team Utility accounting unit; taxi excluded from starter candidates.

## Readiness summary

- Baked PLAYER_DB rows with `proj2026`: **541**
- Teams able to fill all 17 legal starter slots without a non-K projection fallback: **12 / 12**
- Median active non-K roster coverage: **93.45%**
- Median actual non-K Sleeper-starter coverage: **100.0%**
- Actual non-K current starters missing `proj2026`: **3**
- Active roster key gaps where another projection source has signal: **17**

## Agreement with validated blend

- Active players with both baked `proj2026` and blend signal: **412**
- Spearman correlation, baked `proj2026` vs blend: **0.9742**
- Median absolute point difference: **5.78**
- Median starter overlap, baked `proj2026` vs blend-optimal: **16.0 / 17**
- Complete blend evaluations for baked-projection lineup: **12 / 12**
- Median blend points left on table by baked-projection lineup: **9.43**
- Median blend points left on table by current FV lineup: **128.47**

## Team detail

| Team | Active proj cov. | Actual starter cov. | Missing selected proj | Prod/Blend overlap | Prod points left | FV points left |
|---|---:|---:|---:|---:|---:|---:|
| Moose Knuckles | 94.6% | 100.0% | 0 | 16/17 | 68.9 | 135.4 |
| Apex Predators | 92.5% | 100.0% | 0 | 16/17 | 48.7 | 217.6 |
| Serious Gourmet Shit | 97.2% | 93.8% | 0 | 15/17 | 22.9 | 59.4 |
| Narroway Farms M714 | 97.5% | 100.0% | 0 | 15/17 | 16.8 | 194.6 |
| <respectable team name> | 89.5% | 100.0% | 0 | 15/17 | 11.0 | n/a |
| Cock Mchorse 🐴 | 95.0% | 100.0% | 0 | 16/17 | 9.6 | 227.9 |
| Landry's Hat | 94.4% | 100.0% | 0 | 16/17 | 9.3 | 88.1 |
| Pullham Bluecocks  | 97.3% | 100.0% | 0 | 15/17 | 5.7 | 99.8 |
| Sunday Brunson  | 92.3% | 93.8% | 0 | 15/17 | 1.9 | n/a |
| Just Run Power | 87.5% | 100.0% | 0 | 17/17 | 0.0 | 270.7 |
| Jersey Bagels | 89.2% | 93.8% | 0 | 17/17 | 0.0 | 81.7 |
| Toddy2times | 90.0% | 100.0% | 0 | 17/17 | 0.0 | 121.5 |

## Current starters missing baked `proj2026`

- Sunday Brunson : Parker Washington (WR, Sleeper 9487, key `parker washington`)
- Jersey Bagels: Joey Bosa (DL, Sleeper 3156, key `joey bosa`)
- Serious Gourmet Shit: Caleb Downs (DB, Sleeper 13376, key `caleb downs`)

## Runtime key gaps with projection signal elsewhere

- Just Run Power: Xavier Hutchinson (WR, Sleeper 10218, live key `xavier hutchinson`, external projection 54.6)
- Just Run Power: Jacob Saylors (RB, Sleeper 11237, live key `jacob saylors`, external projection 1.3)
- Just Run Power: Devaughn Vele (WR, Sleeper 11834, live key `devaughn vele`, external projection 119.3)
- Just Run Power: Akeem Davis-Gaither (LB, Sleeper 6860, live key `akeem davisgaither`, external projection 159.0)
- Sunday Brunson : Parker Washington (WR, Sleeper 9487, live key `parker washington`, external projection 164.8)
- Sunday Brunson : Jamal Haynes (RB, Sleeper 13946, live key `jamal haynes`, external projection 6.1)
- Landry's Hat: Riley Moss (DB, Sleeper 10930, live key `riley moss`, external projection 139.5)
- Landry's Hat: Darren Waller (TE, Sleeper 2505, live key `darren waller`, external projection 108.9)
- Pullham Bluecocks : Sione Vaki (RB, Sleeper 11729, live key `sione vaki`, external projection 3.0)
- Cock Mchorse 🐴: Charlie Kolar (TE, Sleeper 8127, live key `charlie kolar`, external projection 53.7)
- Apex Predators: Bobby Okereke (LB, Sleeper 5944, live key `bobby okereke`, external projection 227.9)
- Toddy2times: Avieon Terrell (DB, Sleeper 13389, live key `avieon terrell`, external projection 42.5)
- Toddy2times: Aaron Donald (DL, Sleeper 2227, live key `aaron donald`, external projection 89.2)
- Toddy2times: Bradley Chubb (DL, Sleeper 4967, live key `bradley chubb`, external projection 123.0)
- <respectable team name>: DeMarcus Lawrence (DL, Sleeper 2064, live key `demarcus lawrence`, external projection 119.0)
- <respectable team name>: Kayshon Boutte (WR, Sleeper 9504, live key `kayshon boutte`, external projection 122.7)
- Serious Gourmet Shit: Caleb Downs (DB, Sleeper 13376, live key `caleb downs`, external projection 164.0)

## Guardrails

- This does not calibrate TU_BENCH_WEIGHT.
- This does not replace Fundamental Value with projected points.
- Missing proj2026 is treated as a fallback condition, not as a zero projection.
- Taxi players are excluded from starter candidates because they are not currently startable without activation.
- The blend is an evaluation reference, not automatically the production source.

