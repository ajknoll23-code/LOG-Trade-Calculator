# Age Curve V2 — Phase 3 Current-Player Shadow Audit

Method: `age-curve-v2-phase3-shadow-audit-v1`  
Status: **`RESEARCH_ONLY_CURRENT_PLAYER_AGE_SHADOW_AUDIT`**

## Guardrail

**Research only. No deployed AGE_CURVE or player value is changed.**

- Tracked players: **549**
- Real-history players eligible for empirical age shadow: **441**
- No-history players isolated at deployed age factor: **108**

## Candidate movement

| Variant | Changed | Median abs Δ | P90 abs Δ |
|---|---:|---:|---:|
| `deployed_control` | 0 | — | — |
| `empirical_position_age_k25` | 441 | 22.9% | 38.9% |
| `empirical_tier_age_k25` | 441 | 27.6% | 51.7% |
| `empirical_tier_age_k50` | 441 | 24.0% | 43.5% |

## Position-level rank stability

| Variant | Pos | N | Changed | Median abs Δ | Spearman | Top-24 overlap | Max rank move |
|---|---|---:|---:|---:|---:|---:|---:|
| `empirical_position_age_k25` | QB | 64 | 49 | 20.5% | 0.9609 | 91.7% | 15 |
| `empirical_position_age_k25` | RB | 97 | 77 | 27.4% | 0.9740 | 100.0% | 18 |
| `empirical_position_age_k25` | WR | 114 | 85 | 22.9% | 0.9600 | 79.2% | 27 |
| `empirical_position_age_k25` | TE | 44 | 34 | 21.2% | 0.9099 | 91.7% | 16 |
| `empirical_position_age_k25` | DL | 86 | 74 | 20.6% | 0.7949 | 75.0% | 53 |
| `empirical_position_age_k25` | LB | 79 | 64 | 24.3% | 0.8053 | 70.8% | 45 |
| `empirical_position_age_k25` | DB | 65 | 58 | 23.1% | 0.7545 | 70.8% | 39 |
| `empirical_tier_age_k25` | QB | 64 | 49 | 16.7% | 0.9429 | 87.5% | 20 |
| `empirical_tier_age_k25` | RB | 97 | 77 | 29.9% | 0.9404 | 95.8% | 34 |
| `empirical_tier_age_k25` | WR | 114 | 85 | 30.2% | 0.8414 | 70.8% | 51 |
| `empirical_tier_age_k25` | TE | 44 | 34 | 24.3% | 0.8414 | 79.2% | 21 |
| `empirical_tier_age_k25` | DL | 86 | 74 | 23.0% | 0.5822 | 54.2% | 63 |
| `empirical_tier_age_k25` | LB | 79 | 64 | 31.7% | 0.5776 | 58.3% | 53 |
| `empirical_tier_age_k25` | DB | 65 | 58 | 28.0% | 0.3342 | 54.2% | 51 |
| `empirical_tier_age_k50` | QB | 64 | 49 | 16.8% | 0.9544 | 91.7% | 20 |
| `empirical_tier_age_k50` | RB | 97 | 77 | 28.4% | 0.9643 | 95.8% | 24 |
| `empirical_tier_age_k50` | WR | 114 | 85 | 25.1% | 0.9066 | 75.0% | 42 |
| `empirical_tier_age_k50` | TE | 44 | 34 | 22.5% | 0.8649 | 79.2% | 21 |
| `empirical_tier_age_k50` | DL | 86 | 74 | 22.7% | 0.6389 | 58.3% | 64 |
| `empirical_tier_age_k50` | LB | 79 | 64 | 27.9% | 0.6258 | 58.3% | 53 |
| `empirical_tier_age_k50` | DB | 65 | 58 | 26.1% | 0.4113 | 54.2% | 53 |

## Largest movers — `empirical_tier_age_k25`

| Player | Pos | Age | Tier | Deployed age | Shadow age | Current | Shadow | Change |
|---|---|---:|---|---:|---:|---:|---:|---:|
| nic scourton | DL | 21 | depth | 0.655 | 1.362 | 1649 | 3428 | +107.9% |
| shemar stewart | DL | 22 | depth | 0.727 | 1.500 | 1055 | 2175 | +106.2% |
| shemar james | LB | 22 | depth | 0.732 | 1.500 | 1389 | 2846 | +104.9% |
| mykel williams | DL | 22 | depth | 0.747 | 1.500 | 1454 | 2919 | +100.8% |
| james pearce | LB | 22 | depth | 0.749 | 1.500 | 1808 | 3619 | +100.2% |
| walter nolen | DL | 22 | depth | 0.764 | 1.500 | 1803 | 3542 | +96.5% |
| mason graham | DL | 22 | depth | 0.771 | 1.500 | 1962 | 3816 | +94.5% |
| jalon walker | DL | 22 | depth | 0.773 | 1.500 | 2010 | 3899 | +94.0% |
| jihaad campbell | LB | 22 | depth | 0.775 | 1.500 | 2473 | 4784 | +93.4% |
| elijah arroyo | TE | 23 | depth | 0.782 | 1.500 | 680 | 1306 | +92.1% |
| terrance ferguson | TE | 23 | depth | 0.800 | 1.500 | 1126 | 2111 | +87.5% |
| lequint allen | RB | 22 | depth | 0.793 | 1.482 | 582 | 1088 | +86.9% |
| gunnar helm | TE | 23 | depth | 0.816 | 1.500 | 1543 | 2835 | +83.7% |
| mason taylor | TE | 22 | depth | 0.706 | 1.279 | 1079 | 1956 | +81.3% |
| chris brazzell | WR | 22 | depth | 0.700 | 1.267 | 578 | 1045 | +80.8% |
| kevin winston | DB | 22 | depth | 0.832 | 1.500 | 2079 | 3747 | +80.2% |
| jacob parrish | DB | 22 | depth | 0.839 | 1.500 | 2275 | 4067 | +78.8% |
| malaki starks | DB | 22 | depth | 0.844 | 1.500 | 2411 | 4286 | +77.8% |
| danny stutsman | LB | 23 | depth | 0.865 | 1.500 | 1585 | 2749 | +73.4% |
| kyle williams | WR | 23 | depth | 0.850 | 1.473 | 701 | 1215 | +73.3% |
| jack bech | WR | 23 | depth | 0.855 | 1.473 | 950 | 1636 | +72.2% |
| malik benson | WR | 23 | depth | 0.857 | 1.473 | 1037 | 1782 | +71.8% |
| jaylin noel | WR | 23 | depth | 0.858 | 1.473 | 1061 | 1822 | +71.7% |
| pat bryant | WR | 23 | depth | 0.862 | 1.473 | 1261 | 2154 | +70.8% |
| keon coleman | WR | 23 | depth | 0.863 | 1.473 | 1315 | 2244 | +70.6% |

## Largest movers — `empirical_tier_age_k50`

| Player | Pos | Age | Tier | Deployed age | Shadow age | Current | Shadow | Change |
|---|---|---:|---|---:|---:|---:|---:|---:|
| shemar stewart | DL | 22 | depth | 0.727 | 1.500 | 1055 | 2175 | +106.2% |
| mykel williams | DL | 22 | depth | 0.747 | 1.500 | 1454 | 2919 | +100.8% |
| walter nolen | DL | 22 | depth | 0.764 | 1.500 | 1803 | 3542 | +96.5% |
| mason graham | DL | 22 | depth | 0.771 | 1.500 | 1962 | 3816 | +94.5% |
| jalon walker | DL | 22 | depth | 0.773 | 1.500 | 2010 | 3899 | +94.0% |
| elijah arroyo | TE | 23 | depth | 0.782 | 1.500 | 680 | 1306 | +92.1% |
| terrance ferguson | TE | 23 | depth | 0.800 | 1.500 | 1126 | 2111 | +87.5% |
| shemar james | LB | 22 | depth | 0.732 | 1.351 | 1389 | 2564 | +84.6% |
| gunnar helm | TE | 23 | depth | 0.816 | 1.500 | 1543 | 2835 | +83.7% |
| james pearce | LB | 22 | depth | 0.749 | 1.351 | 1808 | 3261 | +80.4% |
| kevin winston | DB | 22 | depth | 0.832 | 1.500 | 2079 | 3747 | +80.2% |
| nic scourton | DL | 21 | depth | 0.655 | 1.176 | 1649 | 2960 | +79.5% |
| jacob parrish | DB | 22 | depth | 0.839 | 1.500 | 2275 | 4067 | +78.8% |
| malaki starks | DB | 22 | depth | 0.844 | 1.500 | 2411 | 4286 | +77.8% |
| jihaad campbell | LB | 22 | depth | 0.775 | 1.351 | 2473 | 4311 | +74.3% |
| lequint allen | RB | 22 | depth | 0.793 | 1.320 | 582 | 969 | +66.5% |
| chris brazzell | WR | 22 | depth | 0.700 | 1.147 | 578 | 946 | +63.7% |
| danny stutsman | LB | 23 | depth | 0.865 | 1.398 | 1585 | 2563 | +61.7% |
| mason taylor | TE | 22 | depth | 0.706 | 1.139 | 1079 | 1741 | +61.4% |
| teddye buchanan | LB | 23 | depth | 0.879 | 1.398 | 2356 | 3748 | +59.1% |
| dylan sampson | RB | 21 | rotation | 0.805 | 1.276 | 1497 | 2374 | +58.6% |
| tee higgins | WR | 27 | starter | 1.000 | 0.504 | 5121 | 2579 | -49.6% |
| michael pittman | WR | 28 | rotation | 1.000 | 0.504 | 3713 | 1870 | -49.6% |
| christian watson | WR | 27 | starter | 1.000 | 0.504 | 4493 | 2263 | -49.6% |
| devonta smith | WR | 27 | starter | 1.000 | 0.504 | 4604 | 2319 | -49.6% |

## Largest movers — `empirical_position_age_k25`

| Player | Pos | Age | Tier | Deployed age | Shadow age | Current | Shadow | Change |
|---|---|---:|---|---:|---:|---:|---:|---:|
| nic scourton | DL | 21 | depth | 0.655 | 1.066 | 1649 | 2683 | +62.7% |
| shemar stewart | DL | 22 | depth | 0.727 | 1.146 | 1055 | 1662 | +57.5% |
| mykel williams | DL | 22 | depth | 0.747 | 1.146 | 1454 | 2231 | +53.4% |
| walter nolen | DL | 22 | depth | 0.764 | 1.146 | 1803 | 2707 | +50.1% |
| mason graham | DL | 22 | depth | 0.771 | 1.146 | 1962 | 2916 | +48.6% |
| jalon walker | DL | 22 | depth | 0.773 | 1.146 | 2010 | 2980 | +48.3% |
| mason taylor | TE | 22 | depth | 0.706 | 1.034 | 1079 | 1581 | +46.5% |
| shemar james | LB | 22 | depth | 0.732 | 1.067 | 1389 | 2024 | +45.7% |
| geno smith | QB | 35 | rotation | 0.546 | 0.794 | 1897 | 2760 | +45.5% |
| chris brazzell | WR | 22 | depth | 0.700 | 1.010 | 578 | 833 | +44.1% |
| elijah arroyo | TE | 23 | depth | 0.782 | 1.126 | 680 | 980 | +44.1% |
| james pearce | LB | 22 | depth | 0.749 | 1.067 | 1808 | 2574 | +42.4% |
| abdul carter | DL | 22 | starter | 0.815 | 1.146 | 2956 | 4160 | +40.7% |
| terrance ferguson | TE | 23 | depth | 0.800 | 1.126 | 1126 | 1584 | +40.7% |
| tj hockenson | TE | 29 | rotation | 1.000 | 0.601 | 2305 | 1384 | -40.0% |
| juwan johnson | TE | 29 | rotation | 1.000 | 0.601 | 2932 | 1761 | -39.9% |
| frankie luvu | LB | 29 | depth | 1.000 | 0.601 | 3074 | 1848 | -39.9% |
| zack baun | LB | 29 | starter | 1.000 | 0.601 | 4735 | 2847 | -39.9% |
| fred warner | LB | 29 | starter | 1.000 | 0.601 | 4743 | 2852 | -39.9% |
| roquan smith | LB | 29 | starter | 1.000 | 0.601 | 4718 | 2837 | -39.9% |
| quincy williams | LB | 29 | starter | 1.000 | 0.601 | 4229 | 2543 | -39.9% |
| christian rozeboom | LB | 29 | depth | 1.000 | 0.601 | 2639 | 1587 | -39.9% |
| azeez alshaair | LB | 29 | rotation | 1.000 | 0.601 | 3841 | 2310 | -39.9% |
| dre greenlaw | LB | 29 | depth | 1.000 | 0.601 | 3081 | 1853 | -39.9% |
| justin jefferson | WR | 27 | rotation | 1.000 | 0.603 | 3702 | 2232 | -39.7% |

## Integrity

- Deployed control zero movement: **PASS**
- No-history players zero movement in every candidate: **PASS**
- Full tracked-player coverage in every variant: **PASS**

## Next step

If current-player movement is stable and position/tier behavior is sensible, freeze the surviving age candidates before 2026 evidence and grade them prospectively against future realized outcomes.
