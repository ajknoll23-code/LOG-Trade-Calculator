# IDP V1 Preferred Bake Preview

## Status

**Preview only. Production `index.html` has not been modified.**

- Preferred candidate method: `reproducible_old_vs_v1_model_delta_transported_to_true_live_prod_mult`
- Live IDP keys in candidate: **404**
- Actual PROD_MULT entries that would change: **324**
- Exact holds / unchanged candidate entries: **80**
- Candidate HTML parsed/evaluated successfully: **565 PLAYER_DB rows**

## Changed entries by position

- LB: **117**
- DL: **91**
- DB: **116**

## Changed entries by source cohort

- `both`: **271**
- `fp_only`: **12**
- `sleeper_only`: **41**

## Changed entries by status

- `model_delta_transported`: **324**

## Known anchors

| Player | Pos | Old | Candidate | Change |
|---|---|---:|---:|---:|
| bradley chubb | LB | 0.4110 | 0.5580 | +35.8% |
| aidan hutchinson | DL | 0.9940 | 1.0559 | +6.2% |
| myles garrett | DL | 1.1310 | 1.1966 | +5.8% |
| fred warner | LB | 0.7730 | 0.7699 | -0.4% |
| roquan smith | LB | 0.7760 | 0.7659 | -1.3% |
| ej speed | LB | 0.2070 | 0.1953 | -5.7% |
| isaiah mcduffie | LB | 0.3740 | 0.2774 | -25.8% |

## Largest raw PROD_MULT changes

| Player | Pos | Old | New | Change | Cohort |
|---|---|---:|---:|---:|---|
| denzel perryman | LB | 0.1730 | 0.2590 | +49.7% | both |
| aj haulcy | DB | 0.2120 | 0.3012 | +42.1% | both |
| bradley chubb | LB | 0.4110 | 0.5580 | +35.8% | both |
| eric murray | DB | 0.3080 | 0.3980 | +29.2% | both |
| dmarco jackson | LB | 0.2140 | 0.1556 | -27.3% | both |
| omar speights | LB | 0.2820 | 0.3564 | +26.4% | both |
| khalil mack | LB | 0.2130 | 0.2686 | +26.1% | both |
| isaiah mcduffie | LB | 0.3740 | 0.2774 | -25.8% | both |
| christian elliss | LB | 0.3040 | 0.3799 | +25.0% | both |
| mike hughes | DB | 0.2750 | 0.3417 | +24.3% | both |
| cody barton | LB | 0.4080 | 0.5060 | +24.0% | both |
| trevin wallace | LB | 0.3380 | 0.4189 | +23.9% | both |
| jevon holland | DB | 0.3410 | 0.4206 | +23.3% | both |
| christian harris | LB | 0.2830 | 0.3485 | +23.1% | both |
| justin strnad | LB | 0.2820 | 0.3471 | +23.1% | both |
| jacob rodriguez | LB | 0.2560 | 0.3150 | +23.0% | both |
| craig woodson | DB | 0.4040 | 0.4960 | +22.8% | both |
| jake golday | LB | 0.1500 | 0.1841 | +22.7% | both |
| nohl williams | DB | 0.3810 | 0.2954 | -22.5% | both |
| derrick barnes | LB | 0.3620 | 0.4392 | +21.3% | both |
| andrew mukuba | DB | 0.3370 | 0.3965 | +17.7% | both |
| dru phillips | DB | 0.6750 | 0.7903 | +17.1% | both |
| jiayir brown | DB | 0.4340 | 0.5078 | +17.0% | both |
| javon bullard | DB | 0.3490 | 0.4076 | +16.8% | both |
| jaylen watson | DB | 0.5140 | 0.5986 | +16.5% | both |

## Safety gates passed

- Current `index.html` canonical PROD_MULT entries exactly match the immutable pre-V1 baseline before preview generation.
- Only the `PROD_MULT_DATA` object is changed in the preview patch.
- Node JavaScript syntax check passes on the temporary candidate HTML.
- `snapshot_values.py` parses and evaluates the temporary candidate HTML successfully.
- No git commit or push is performed by this script.

## Production note

The large explanatory comment immediately above `PROD_MULT_DATA` still describes the retired manual FantasyPros/Sleeper final-points blend. When the final V1 bake is approved, update that comment in the same reviewed production commit so the code documentation matches the new model.
