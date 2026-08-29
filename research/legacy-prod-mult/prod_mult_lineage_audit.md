# PROD_MULT Lineage Audit

## Verdict

The current legacy generator does **not** reproduce the immutable pre-V1 baked production table. This report treats that as lineage drift; it does not assume the generator or the baked table is inherently correct.

## Overall

- Immutable live baseline entries: **823**
- Generated player records: **1125**
- Overlapping keys: **813**
- Overlap with a generated prod_mult: **695**
- Exact matches: **58**
- Live keys absent from generated universe: **10**
- Median absolute prod_mult drift: **0.0339**
- P90 absolute drift: **0.1328**
- P95 absolute drift: **0.1806**
- Maximum absolute drift: **0.3399**

## Drift by position

| Pos | N | Median abs | P90 | P95 | Max |
|---|---:|---:|---:|---:|---:|
| DB | 117 | 0.0211 | 0.1609 | 0.1826 | 0.2799 |
| DL | 93 | 0.0382 | 0.1728 | 0.2398 | 0.3399 |
| LB | 119 | 0.0238 | 0.1852 | 0.2182 | 0.2901 |
| QB | 55 | 0.0032 | 0.0242 | 0.0426 | 0.1251 |
| RB | 111 | 0.0577 | 0.1269 | 0.1470 | 0.3268 |
| TE | 67 | 0.0210 | 0.0856 | 0.1271 | 0.2136 |
| WR | 133 | 0.0513 | 0.1145 | 0.1380 | 0.2470 |

## Drift by legacy projection-source cohort

| Source | N | Median abs | P90 | P95 | Max |
|---|---:|---:|---:|---:|---:|
| blend_50_50 | 409 | 0.0309 | 0.1210 | 0.1652 | 0.3399 |
| fantasypros_only | 42 | 0.0014 | 0.0833 | 0.1088 | 0.1957 |
| sleeper_only | 244 | 0.0500 | 0.1612 | 0.2003 | 0.3034 |

## Largest absolute drifts

| Player key | Pos | Live | Generated | Signed diff | Legacy projection source |
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
| harold landry | LB | 0.7410 | 0.5235 | -0.2175 | sleeper_only |
| darren waller | TE | 0.3420 | 0.5556 | +0.2136 | sleeper_only |
| jaylinn hawkins | DB | 0.6730 | 0.4648 | -0.2082 | sleeper_only |
| alex highsmith | LB | 0.7660 | 0.5590 | -0.2070 | blend_50_50 |
| abdul carter | LB | 0.6670 | 0.4616 | -0.2054 | blend_50_50 |
| joey porter | DB | 0.2930 | 0.4978 | +0.2048 | sleeper_only |
| jaelan phillips | LB | 0.6640 | 0.4600 | -0.2040 | sleeper_only |
| maliek collins | DL | 0.3880 | 0.5896 | +0.2016 | sleeper_only |
| micah parsons | LB | 0.7080 | 0.5090 | -0.1990 | blend_50_50 |
| avieon terrell | DB | 0.1620 | 0.3577 | +0.1957 | fantasypros_only |
| caleb douglas | WR | 0.1770 | 0.3704 | +0.1934 | blend_50_50 |
| pat surtain | DB | 0.2820 | 0.4752 | +0.1932 | sleeper_only |
| nick herbig | LB | 0.6440 | 0.4538 | -0.1902 | blend_50_50 |
| cashius howell | DL | 0.1500 | 0.3369 | +0.1869 | sleeper_only |
| malachi fields | WR | 0.1500 | 0.3367 | +0.1867 | blend_50_50 |

## Interpretation

- The durability files being restored makes the legacy generator runnable, but does **not** make it historically identical to the baked production table.
- Therefore a new V1 bake must not describe the legacy generated JSON as the true old production baseline.
- The immutable baked baseline should be used for user-visible before/after comparisons.
- Reusable history/durability computation should be separated from the obsolete legacy projection blend before the V1 path is considered canonical.

## Generated replacement baselines (diagnostic only)

- QB: 242.8506
- RB: 176.2254
- WR: 154.3070
- TE: 129.6120
- DL: 132.0037
- LB: 184.1543
- DB: 156.1561
