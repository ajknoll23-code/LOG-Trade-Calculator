# Production V2 — Phase 3 Baseline Normalization Audit

## Decision

**Carry the evidence-hybrid replacement ranks forward as a V2 normalization candidate; do not deploy them yet.**

This audit changed only the replacement denominator. Provider blend, history/forward weighting, transform, age, role floors, position weights, and global value scale were all held fixed.

- Documented scenario reproduced Phase 1 exactly: **Yes**
- Maximum reproduction delta: **0**
- Production files mutated: **0**

## Replacement-rank evidence

| Pos | Documented | Evidence hybrid | Test-3 source | Doc MAE | Evidence MAE | 4wk folds won |
|---|---:|---:|---|---:|---:|---:|
| QB | 18 | 18 | retain_documented_no_competing_candidate | — | — | — |
| RB | 32 | 26 | roster_economics_informed | 0.2774 | 0.2391 | 15 |
| WR | 36 | 34 | roster_economics_informed | 0.2485 | 0.2443 | 15 |
| TE | 15 | 15 | documented | 0.2213 | 0.2213 | 10 |
| DL | 32 | 23 | legacy_empirical | 0.2551 | 0.2280 | 15 |
| LB | 32 | 32 | retain_documented_no_competing_candidate | — | — | — |
| DB | 32 | 30 | legacy_empirical | 0.2228 | 0.2219 | 15 |

## 2026 Phase-1 blast radius from changing only the denominator

| Pos | PW fixed | Doc anchor | Hybrid anchor | Baseline pts Δ | Median FV Δ | P95 abs FV Δ | Median PM Δ |
|---|---:|---|---|---:|---:|---:|---:|
| QB | 1.30 | 18 jordan love | 18 jordan love | +0.0% | +0.0% | 0.0% | +0.0000 |
| RB | 0.89 | 32 bhayshul tuten | 26 treveyon henderson | +21.1% | -19.7% | 25.1% | -0.0960 |
| WR | 1.00 | 36 stefon diggs | 34 quentin johnston | +0.9% | -1.1% | 1.3% | -0.0052 |
| TE | 0.82 | 15 juwan johnson | 15 juwan johnson | +0.0% | +0.0% | 0.0% | +0.0000 |
| DL | 0.93 | 32 ed oliver | 23 abdul carter | +3.6% | -4.1% | 5.2% | -0.0243 |
| LB | 1.12 | 32 tj edwards | 32 tj edwards | +0.0% | +0.0% | 0.0% | +0.0000 |
| DB | 0.87 | 32 jalen pitre | 30 daron bland | +0.3% | -0.4% | 0.4% | -0.0024 |

## Structural scarcity-overlap interpretation

A deeper replacement rank lowers the denominator and increases `PROD_MULT` across that position. `POSITION_WEIGHT` is a separate explicit position-level multiplier. Therefore both layers can create position-level leverage.

**This audit does not claim double counting is proven.** It does establish that the two mechanisms overlap structurally, so Production V2 should keep their jobs separate: production normalization should be justified by production evidence; positional economics should remain in `POSITION_WEIGHT` / roster economics.

The evidence-hybrid mostly moves replacement anchors shallower (RB 32→26, WR 36→34, DL 32→23, DB 32→30), which removes some denominator-driven inflation while leaving the explicit position weights untouched.

## Largest value movers from denominator-only change

| Player | Pos | Documented | Hybrid | Change | PM documented→hybrid |
|---|---|---:|---:|---:|---|
| adam randall | RB | 859 | 634 | -26.2% | 0.215→0.160 |
| isaiah davis | RB | 1012 | 750 | -25.9% | 0.207→0.153 |
| malik davis | RB | 832 | 619 | -25.6% | 0.215→0.160 |
| kaytron allen | RB | 1097 | 820 | -25.3% | 0.224→0.167 |
| eli heidenreich | RB | 1096 | 820 | -25.2% | 0.224→0.167 |
| nicholas singleton | RB | 1088 | 816 | -25.0% | 0.240→0.180 |
| demond claiborne | RB | 1135 | 852 | -24.9% | 0.237→0.178 |
| sean tucker | RB | 1135 | 852 | -24.9% | 0.232→0.174 |
| tank bigsby | RB | 1166 | 878 | -24.7% | 0.238→0.179 |
| emanuel wilson | RB | 981 | 739 | -24.7% | 0.243→0.183 |
| seth mcgowan | RB | 1186 | 894 | -24.6% | 0.242→0.183 |
| braelon allen | RB | 1188 | 899 | -24.3% | 0.264→0.200 |
| jeremiyah love | RB | 3125 | 2377 | -23.9% | 0.813→0.653 |
| brian robinson | RB | 1079 | 821 | -23.9% | 0.271→0.206 |
| dylan sampson | RB | 1356 | 1035 | -23.7% | 0.347→0.269 |
| emmett johnson | RB | 1381 | 1055 | -23.6% | 0.288→0.220 |
| mike washington | RB | 1421 | 1087 | -23.5% | 0.290→0.222 |
| jonah coleman | RB | 1477 | 1134 | -23.2% | 0.302→0.232 |
| justice hill | RB | 1047 | 804 | -23.2% | 0.301→0.231 |
| phil mafah | RB | 955 | 734 | -23.1% | 0.195→0.150 |
| keaton mitchell | RB | 1556 | 1199 | -22.9% | 0.318→0.245 |
| kaelon black | RB | 1647 | 1274 | -22.6% | 0.336→0.260 |
| kimani vidal | RB | 1655 | 1281 | -22.6% | 0.339→0.262 |
| jmari taylor | RB | 881 | 1077 | +22.2% | 0.180→0.220 |
| isiah pacheco | RB | 1484 | 1156 | -22.1% | 0.375→0.292 |

## Why this is not a deployment

The replacement-rank evidence is temporally valid, but the provider blend and history-vs-forward weights remain prospectively uncalibrated. Phase 3 isolates denominator behavior only.

The baseline backtester itself also has a known limitation: it isolated the denominator using trailing PPG because historical provider snapshots were unavailable. Phase 2A has now fixed that problem prospectively for 2026, but realized evidence has not accumulated yet.

## Next Production V2 step

Carry both normalization candidates into the later prospective evaluation. In parallel, the next structural audit can test the linear `clamp(-0.10 + 0.75 × ratio, 0.15, 1.55)` transform and especially its floor/ceiling compression without changing production.
