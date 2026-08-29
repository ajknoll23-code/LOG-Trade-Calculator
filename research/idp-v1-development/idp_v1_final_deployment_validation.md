# IDP V1 Final Production Deployment Validation

## Verdict

**PASS — the live `index.html` PROD_MULT table exactly matches the approved model-delta transport deployment.**

- Deployment method: `reproducible_old_vs_v1_model_delta_transported_to_true_live_prod_mult`
- Immutable pre-V1 PROD_MULT entries: **823**
- Candidate IDP keys: **404**
- Approved/deployed raw PROD_MULT changes: **320**
- Exact candidate holds: **84**
- Floor-rescue discontinuity guards: **4**
- Non-IDP final-value changes: **0**
- Legacy/current position mismatches intentionally isolated: **46**

## Internal V1 replacement-baseline movement

- LB: **+3.4%**
- DL: **+4.4%**
- DB: **+3.4%**

## True live old → deployed raw PROD_MULT movement

| Pos | N | Median | P90 | P95 | Min | Max |
|---|---:|---:|---:|---:|---:|---:|
| LB | 77 | -0.5% | +1.7% | +2.6% | -5.8% | +23.0% |
| DL | 86 | +3.3% | +7.1% | +8.1% | -12.7% | +13.4% |
| DB | 64 | +0.3% | +3.1% | +5.1% | -7.1% | +42.1% |

## True live old → deployed final Trade Desk value movement

| Pos | N | Median | P90 | P95 | Min | Max |
|---|---:|---:|---:|---:|---:|---:|
| LB | 79 | -0.5% | +1.7% | +2.5% | -6.5% | +23.9% |
| DL | 86 | +3.3% | +7.3% | +8.2% | -12.6% | +13.4% |
| DB | 65 | +0.2% | +3.1% | +5.2% | -7.1% | +44.5% |

## Rank stability

| Pos | Top-24 movers >=5 | Top-36 movers >=5 | Max abs top-36 move |
|---|---:|---:|---:|
| LB | 1 | 1 | 5 |
| DL | 4 | 7 | 8 |
| DB | 1 | 2 | 5 |

## Source-cohort behavior

| Cohort | N candidate | Raw PROD_MULT median | Raw P95 | Final-value median* | Final P95* |
|---|---:|---:|---:|---:|---:|
| both | 273 | +2.0% | +22.9% | +1.1% | +7.9% |
| fp_only | 35 | +0.0% | +1.8% | -3.0% | +4.4% |
| no_new_data | 52 | +0.0% | +0.0% | +0.0% | +0.0% |
| sleeper_only | 44 | -4.0% | +0.0% | -3.8% | +0.8% |

* Final-value cohort summaries include only candidate keys that are present in current `PLAYER_DB`.

## Raw clamp occupancy among the 404 candidate IDPs

- Pre-V1 floor 0.15: **25**
- Deployed floor 0.15: **24**
- Pre-V1 ceiling 1.55: **0**
- Deployed ceiling 1.55: **0**

## Known anchors

| Player | Pos | Old raw | New raw | Raw change | Old value | New value | Final change | Rank move | Cohort |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| bradley chubb | DL | 0.4110 | 0.5580 | +35.8% | — | — | — | — | both |
| aidan hutchinson | DL | 0.9940 | 1.0559 | +6.2% | 5084 | 5401 | +6.2% | +0 | both |
| myles garrett | DL | 1.1310 | 1.1966 | +5.8% | 5345 | 5655 | +5.8% | -1 | both |
| fred warner | LB | 0.7730 | 0.7699 | -0.4% | 4762 | 4743 | -0.4% | +0 | both |
| roquan smith | LB | 0.7760 | 0.7659 | -1.3% | 4780 | 4718 | -1.3% | +5 | both |
| ej speed | LB | 0.2070 | 0.1953 | -5.7% | — | — | — | — | sleeper_only |
| isaiah mcduffie | LB | 0.3740 | 0.2774 | -25.8% | — | — | — | — | both |

## Largest final-value movers

| Player | Pos | Old | New | Change | Rank move | Cohort/status |
|---|---|---:|---:|---:|---:|---|
| aj haulcy | DB | 796 | 1150 | +44.5% | -1 | both/model_delta_transported |
| jacob rodriguez | LB | 1358 | 1682 | +23.9% | -2 | both/model_delta_transported |
| jonathan greenard | DL | 1770 | 2007 | +13.4% | -7 | both/model_delta_transported |
| jadeveon clowney | DL | 2293 | 2003 | -12.6% | +10 | fp_only/model_delta_transported |
| will johnson | DB | 2259 | 2535 | +12.2% | -10 | both/model_delta_transported |
| zach allen | DL | 3708 | 4096 | +10.5% | -6 | both/model_delta_transported |
| zion young | DL | 1162 | 1044 | -10.2% | +3 | fp_only/model_delta_transported |
| chris jones | DL | 2357 | 2579 | +9.4% | -5 | both/model_delta_transported |
| trey hendrickson | DL | 2776 | 3029 | +9.1% | -1 | both/model_delta_transported |
| greg rousseau | DL | 3335 | 3610 | +8.2% | -5 | both/model_delta_transported |
| donovan ezeiruaku | DL | 2208 | 2386 | +8.1% | -6 | both/model_delta_transported |
| derick hall | DL | 2215 | 2037 | -8.0% | +2 | fp_only/model_delta_transported |
| josh hinesallen | DL | 3678 | 3968 | +7.9% | -2 | both/model_delta_transported |
| boye mafe | DL | 2588 | 2789 | +7.8% | -3 | both/model_delta_transported |
| abdul carter | DL | 2749 | 2956 | +7.5% | -1 | both/model_delta_transported |
| klavon chaisson | LB | 2070 | 2221 | +7.3% | -1 | both/model_delta_transported |
| laiatu latu | DL | 3857 | 4132 | +7.1% | -2 | both/model_delta_transported |
| coby bryant | DB | 2512 | 2333 | -7.1% | +8 | sleeper_only/model_delta_transported |
| tuli tuipulotu | DL | 4074 | 4362 | +7.1% | -1 | both/model_delta_transported |
| nick herbig | DL | 3294 | 3525 | +7.0% | -5 | both/model_delta_transported |

## Release attribution

- The OLD side is reconstructed from the immutable pre-V1 `PROD_MULT_DATA` snapshot.
- The NEW side is the actual deployed `index.html`.
- All other valuation constants, age curves, role-floor behavior, and position weights are held identical.
- Offense values are confirmed unchanged.
- The 46 legacy/current IDP position mismatches remain explicitly isolated from this V1 projection release.
