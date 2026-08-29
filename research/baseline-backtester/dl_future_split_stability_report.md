# DL Future-Split Stability Check

Question: does future DL production repeatedly produce a real boundary in the low-to-mid 20s, or does the future split rank bounce around while the median happens to land near 23?

## Window = 2 weeks (15 folds)

| Fold | Split rank | Split PPG | N players |
|---|---|---|---|
| 2024_wk9 | 16 | 15.25 | 232 |
| 2024_wk10 | 13 | 14.25 | 229 |
| 2024_wk11 | 19 | 14.25 | 235 |
| 2024_wk12 | 10 | 17.5 | 237 |
| 2024_wk13 | 23 | 12.0 | 239 |
| 2024_wk14 | 20 | 12.5 | 240 |
| 2024_wk15 | 20 | 11.12 | 240 |
| 2025_wk9 | 7 | 19.75 | 233 |
| 2025_wk10 | 8 | 17.25 | 234 |
| 2025_wk11 | 6 | 17.75 | 234 |
| 2025_wk12 | 10 | 16.62 | 236 |
| 2025_wk13 | 15 | 14.62 | 242 |
| 2025_wk14 | 10 | 15.62 | 241 |
| 2025_wk15 | 15 | 14.12 | 254 |
| 2024_full_to_2025_full | 12 | 12.38 | 261 |

Median: **13**  |  IQR: [10, 16]  |  10th-90th pctile: [7, 20]  |  Range: [6, 23]
Median split PPG value: 14.62

## Window = 4 weeks (15 folds)

| Fold | Split rank | Split PPG | N players |
|---|---|---|---|
| 2024_wk9 | 22 | 12.81 | 242 |
| 2024_wk10 | 21 | 11.69 | 244 |
| 2024_wk11 | 10 | 13.5 | 248 |
| 2024_wk12 | 12 | 13.17 | 248 |
| 2024_wk13 | 18 | 10.81 | 251 |
| 2024_wk14 | 15 | 11.38 | 252 |
| 2024_wk15 | 14 | 11.75 | 250 |
| 2025_wk9 | 15 | 13.83 | 245 |
| 2025_wk10 | 10 | 13.88 | 244 |
| 2025_wk11 | 5 | 16.0 | 246 |
| 2025_wk12 | 15 | 13.38 | 252 |
| 2025_wk13 | 14 | 12.94 | 263 |
| 2025_wk14 | 17 | 12.25 | 264 |
| 2025_wk15 | 16 | 12.5 | 268 |
| 2024_full_to_2025_full | 12 | 12.38 | 261 |

Median: **15**  |  IQR: [12, 16]  |  10th-90th pctile: [10, 21]  |  Range: [5, 22]
Median split PPG value: 12.81

## Window = 6 weeks (11 folds)

| Fold | Split rank | Split PPG | N players |
|---|---|---|---|
| 2024_wk9 | 16 | 12.05 | 247 |
| 2024_wk10 | 26 | 10.7 | 251 |
| 2024_wk11 | 11 | 12.1 | 255 |
| 2024_wk12 | 8 | 13.3 | 254 |
| 2024_wk13 | 21 | 10.25 | 257 |
| 2025_wk9 | 14 | 12.4 | 250 |
| 2025_wk10 | 12 | 12.65 | 252 |
| 2025_wk11 | 17 | 11.6 | 258 |
| 2025_wk12 | 21 | 11.65 | 261 |
| 2025_wk13 | 15 | 12.25 | 271 |
| 2024_full_to_2025_full | 12 | 12.38 | 261 |

Median: **15**  |  IQR: [12, 21]  |  10th-90th pctile: [11, 21]  |  Range: [8, 26]
Median split PPG value: 12.1


## Combined across all windows

Frequency table (rank bucket : count):
    5-9  :   5  #####
   10-14 :  15  ###############
   15-19 :  13  #############
   20-24 :   7  #######
   25-29 :   1  #

Median (all windows combined): **15**  |  IQR: [11, 17]  |  10th-90th: [8, 21]  |  Range: [5, 26]  |  n=41

Block bootstrap of the median split rank (200 resamples): median=15, 10th-90th=[13, 15], range=[10, 16]

## Interpretation guide (not an automatic verdict)

- If most individual-fold split ranks cluster roughly in the low-to-mid 20s (say, 18-28) and the bootstrap 10th-90th interval is reasonably tight around the median: the future production boundary is real and stable -- DL23 is a strong, trustworthy future-production calibration candidate.
- If individual-fold splits are scattered widely (e.g. some folds in the teens, some past 40) even though the median lands near 23: the apparent DL23 advantage is likely being driven by a target that itself isn't stable, and the 10.6% MAE win should be treated with much more caution.
