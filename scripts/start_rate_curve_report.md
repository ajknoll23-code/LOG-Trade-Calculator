# Start-Rate Curve Analysis

Trailing-PPG rank is primary; trailing-cumulative rank is the robustness check. Weeks 1-3 excluded. Zone = (last rank with real start rate >=80%, first rank at/after that point with start rate <=20%).


## QB

- Pooled PPG-rank zone: **(4, 37)**
- Pooled cumulative-rank zone: **(4, 37)**
- PPG vs. cumulative agree (within 6 ranks): **True**
- Baseline comparison uses: **trailing_ppg**
- Documented baseline (18): INSIDE the observed zone (rank 18 is within the real falloff range)
- Empirical baseline (18): INSIDE the observed zone (rank 18 is within the real falloff range)

## RB

- Pooled PPG-rank zone: **(4, 37)**
- Pooled cumulative-rank zone: **(4, 31)**
- PPG vs. cumulative agree (within 6 ranks): **True**
- Baseline comparison uses: **trailing_ppg**
- Documented baseline (32): INSIDE the observed zone (rank 32 is within the real falloff range)
- Empirical baseline (37): INSIDE the observed zone (rank 37 is within the real falloff range)

## WR

- Pooled PPG-rank zone: **(None, None)**
- Pooled cumulative-rank zone: **(1, 43)**
- PPG vs. cumulative agree (within 6 ranks): **False**
- Baseline comparison uses: **trailing_cumulative (PPG-rank zone unresolved)**
- Documented baseline (36): INSIDE the observed zone (rank 36 is within the real falloff range)
- Empirical baseline (43): INSIDE the observed zone (rank 43 is within the real falloff range)

## TE

- Pooled PPG-rank zone: **(None, None)**
- Pooled cumulative-rank zone: **(None, None)**
- PPG vs. cumulative agree (within 6 ranks): **False**
- Baseline comparison uses: **trailing_cumulative (PPG-rank zone unresolved)**
- Documented baseline (15): n/a (zone not resolved)
- Empirical baseline (16): n/a (zone not resolved)

## DL

- Pooled PPG-rank zone: **(7, 55)**
- Pooled cumulative-rank zone: **(4, 49)**
- PPG vs. cumulative agree (within 6 ranks): **True**
- Baseline comparison uses: **trailing_ppg**
- Documented baseline (32): INSIDE the observed zone (rank 32 is within the real falloff range)
- Empirical baseline (23): INSIDE the observed zone (rank 23 is within the real falloff range)

## LB

- Pooled PPG-rank zone: **(None, None)**
- Pooled cumulative-rank zone: **(1, None)**
- PPG vs. cumulative agree (within 6 ranks): **False**
- Baseline comparison uses: **trailing_cumulative (PPG-rank zone unresolved)**
- Documented baseline (32): n/a (zone not resolved)
- Empirical baseline (32): n/a (zone not resolved)

## DB

- Pooled PPG-rank zone: **(None, None)**
- Pooled cumulative-rank zone: **(None, None)**
- PPG vs. cumulative agree (within 6 ranks): **False**
- Baseline comparison uses: **trailing_cumulative (PPG-rank zone unresolved)**
- Documented baseline (32): n/a (zone not resolved)
- Empirical baseline (30): n/a (zone not resolved)

## Overall stability check

PPG-rank and cumulative-rank zones diverge for at least one position -- per the agreed plan, this is the trigger to consider building the preseason/hybrid ranking system. Check the per-position sections above for which one(s).
