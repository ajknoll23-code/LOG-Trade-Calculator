# Draft Capital Outlook V1 — B20 Layer D Shadow Calibration Preregistration

Decision: **PREREGISTER_LAYER_D_SHADOW_CALIBRATION_AUTHORIZE_B21_HISTORICAL_EXECUTION_ONLY**

## Authority entering B20
- B19 C1 classification: STRONG.
- Direct production authority: NO.
- Maximum future initial shadow deviation inherited from B18: +/-3%.

## Frozen Layer D mapping
- One class-wide research-only multiplier; no slot/round/position shaping.
- Fit historical log actual capital on log projected capital with nonnegative OLS slope.
- Neutral point: training median projected log capital.
- Scale: training sample SD of actual log capital.
- Shadow score: predicted deviation from neutral divided by that SD.
- Multiplier: 1 + 0.015 * clip(score, -2, +2).
- Hard bounds: 0.97 to 1.03.

## B21 frozen gates
- D1: numerical validity and positive monotone full-fit slope.
- D2: at least 8/11 LOO direction agreements.
- D3: positive LOO Spearman rho with one-sided 99,999-permutation p <= 0.15.
- D4: <=1.0 percentage-point max single-class-deletion mapping drift on the frozen five-point grid.
- D5: no more than 2/11 historical classes saturated at the +/-3% cap.

## Firewall
- B20 computes no historical shadow multiplier and no B21 gate metric.
- B20 reads no 2027 source content and scores no 2027 class.
- A B21 pass still does not authorize direct 2027 scoring or production.
