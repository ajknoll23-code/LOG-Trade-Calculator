# Roster-Economics Robustness Checks

Dual-eligibility consistency: 1435 players checked, **0 mismatches**.


## QB

- Effective demand (integral under start-rate curve): **27.65**
- Coverage ranks (80% / 90% / 95% of real starts): **24 / 29 / 34**
- 50%-crossing by bin width -- 1: 22, 3: 22, 5: 36 (stable: **False**)
- Bootstrap 50%-crossing: median **22**, 10th-90th percentile **[22, 34]** (200/200 resamples resolved)
- Documented baseline: 18  |  Empirical baseline: 18

## RB

- Effective demand (integral under start-rate curve): **27.03**
- Coverage ranks (80% / 90% / 95% of real starts): **26 / 33 / 39**
- 50%-crossing by bin width -- 1: 26, 3: 25, 5: 26 (stable: **True**)
- Bootstrap 50%-crossing: median **25**, 10th-90th percentile **[25, 28]** (200/200 resamples resolved)
- Documented baseline: 32  |  Empirical baseline: 37

## WR

- Effective demand (integral under start-rate curve): **33.13**
- Coverage ranks (80% / 90% / 95% of real starts): **36 / 43 / 49**
- 50%-crossing by bin width -- 1: 22, 3: 34, 5: 31 (stable: **False**)
- Bootstrap 50%-crossing: median **34**, 10th-90th percentile **[28, 37]** (200/200 resamples resolved)
- Documented baseline: 36  |  Empirical baseline: 43

## TE

- Effective demand (integral under start-rate curve): **19.83**
- Coverage ranks (80% / 90% / 95% of real starts): **21 / 27 / 33**
- 50%-crossing by bin width -- 1: 13, 3: 13, 5: 11 (stable: **True**)
- Bootstrap 50%-crossing: median **13**, 10th-90th percentile **[10, 13]** (200/200 resamples resolved)
- Documented baseline: 15  |  Empirical baseline: 16

## DL

- Effective demand (integral under start-rate curve): **34.37**
- Coverage ranks (80% / 90% / 95% of real starts): **29 / 39 / 47**
- 50%-crossing by bin width -- 1: 17, 3: 34, 5: 36 (stable: **False**)
- Bootstrap 50%-crossing: median **34**, 10th-90th percentile **[16, 37]** (200/200 resamples resolved)
- Documented baseline: 32  |  Empirical baseline: 23

## LB

- Effective demand (integral under start-rate curve): **40.52**
- Coverage ranks (80% / 90% / 95% of real starts): **41 / 50 / 55**
- 50%-crossing by bin width -- 1: 22, 3: 43, 5: 51 (stable: **False**)
- Bootstrap 50%-crossing: median **43**, 10th-90th percentile **[40, 52]** (195/200 resamples resolved)
- Documented baseline: 32  |  Empirical baseline: 32

## DB

- Effective demand (integral under start-rate curve): **36.43**
- Coverage ranks (80% / 90% / 95% of real starts): **38 / 47 / 53**
- 50%-crossing by bin width -- 1: 18, 3: 40, 5: 41 (stable: **False**)
- Bootstrap 50%-crossing: median **28**, 10th-90th percentile **[22, 40]** (200/200 resamples resolved)
- Documented baseline: 32  |  Empirical baseline: 30
