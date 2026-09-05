# Replacement Level / Positional Scale V2 — Phase 2 Historical Backtest

**Research only. No deployment, position-weight, scale, Production V2, or frozen-experiment change is authorized.**

Method: `replacement-level-v2-phase2-historical-backtest-v1`

## Method

This phase reuses the reviewed Revision-2 baseline backtester's **Test 3**. Each fold derives its replacement structure entirely from future production, then scores each training-time candidate rank by MAE/RMSE against that future relative-production structure.

The 4-week window is primary; 2- and 6-week windows are robustness checks. Rolling weekly folds overlap, so fold-win counts are descriptive rather than independent trials. 2024, 2025, and cross-season blocks are reported separately.

Historical provider projection snapshots do not exist, so trailing PPG remains the training numerator. This is a denominator test, not a perfect historical replay of the final blended Production V2 formula.

## Position results

| Pos | Legacy | Prior limited | Phase-2 leader | 4wk leader MAE | Legacy MAE | Δ vs legacy | Window leaders 2/4/6 | Season leaders 2024/2025/cross | Hist pass | Phase-3 shortlist |
|---|---:|---:|---:|---:|---:|---:|---|---|---|---|
| QB | 18 | 18 | 29 | 0.4887 | 0.5574 | -12.3% | 18/29/34 | 34/34/34 | PASS | 18, 29, 34 |
| RB | 32 | 26 | 25 | 0.2295 | 0.2774 | -17.3% | 25/25/25 | 25/25/25 | PASS | 25, 26, 32 |
| WR | 36 | 34 | 28 | 0.2304 | 0.2485 | -7.3% | 28/28/28 | 28/28/28 | PASS | 28, 34, 36 |
| TE | 15 | 15 | 11 | 0.2148 | 0.2213 | -2.9% | 10/11/15 | 10/11/16 | PASS | 10, 11, 15, 16 |
| DL | 32 | 23 | 16 | 0.1937 | 0.2551 | -24.1% | 16/16/16 | 16/16/16 | PASS | 16, 23, 32 |
| LB | 32 | 32 | 28 | 0.1883 | 0.1936 | -2.7% | 28/28/28 | 28/28/28 | PASS | 28, 32 |
| DB | 32 | 30 | 22 | 0.2080 | 0.2228 | -6.6% | 22/22/22 | 22/22/22 | PASS | 22, 30, 32 |

## Candidate detail

### QB

- Legacy control: **18**
- Prior limited Production V2 comparator: **18**
- Primary 4-week leader: **29**
- Same leader across 2/4/6 weeks: **False**
- Historical screen: **PASS**
- Phase-3 shortlist: **18, 29, 34**

| Rank | Median MAE | Mean MAE | Median RMSE | 2024 MAE | 2025 MAE | Cross MAE | Strict fold wins | Best/tied folds | Δ MAE vs legacy |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 14 | 0.5945 | 0.5711 | 0.7313 | 0.5945 | 0.5910 | 0.6226 | 1 | 1 | +6.7% |
| 16 | 0.5798 | 0.5545 | 0.7039 | 0.5670 | 0.5798 | 0.5953 | 1 | 1 | +4.0% |
| 18 | 0.5574 | 0.5388 | 0.6945 | 0.5516 | 0.5741 | 0.5854 | 0 | 0 | +0.0% |
| 20 | 0.5306 | 0.5281 | 0.6815 | 0.5294 | 0.5610 | 0.5722 | 0 | 0 | -4.8% |
| 22 | 0.5247 | 0.5150 | 0.6643 | 0.5188 | 0.5359 | 0.5524 | 0 | 0 | -5.9% |
| 24 | 0.5169 | 0.5115 | 0.6588 | 0.5055 | 0.5354 | 0.5506 | 0 | 0 | -7.3% |
| 28 | 0.4938 | 0.4913 | 0.6270 | 0.4904 | 0.5146 | 0.5049 | 1 | 1 | -11.4% |
| 29 | 0.4887 | 0.4878 | 0.6251 | 0.4806 | 0.5104 | 0.4973 | 3 | 3 | -12.3% |
| 34 | 0.5026 | 0.5110 | 0.6272 | 0.4630 | 0.5080 | 0.4701 | 9 | 9 | -9.8% |

### RB

- Legacy control: **32**
- Prior limited Production V2 comparator: **26**
- Primary 4-week leader: **25**
- Same leader across 2/4/6 weeks: **True**
- Historical screen: **PASS**
- Phase-3 shortlist: **25, 26, 32**

| Rank | Median MAE | Mean MAE | Median RMSE | 2024 MAE | 2025 MAE | Cross MAE | Strict fold wins | Best/tied folds | Δ MAE vs legacy |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 25 | 0.2295 | 0.2275 | 0.3143 | 0.2230 | 0.2392 | 0.2148 | 15 | 15 | -17.3% |
| 26 | 0.2391 | 0.2336 | 0.3276 | 0.2268 | 0.2481 | 0.2185 | 0 | 0 | -13.8% |
| 27 | 0.2420 | 0.2406 | 0.3327 | 0.2391 | 0.2576 | 0.2218 | 0 | 0 | -12.8% |
| 28 | 0.2482 | 0.2470 | 0.3455 | 0.2482 | 0.2609 | 0.2352 | 0 | 0 | -10.5% |
| 30 | 0.2692 | 0.2651 | 0.3616 | 0.2645 | 0.2774 | 0.2432 | 0 | 0 | -3.0% |
| 32 | 0.2774 | 0.2783 | 0.3784 | 0.2769 | 0.2826 | 0.2512 | 0 | 0 | +0.0% |
| 33 | 0.2874 | 0.2895 | 0.3981 | 0.3004 | 0.2863 | 0.2726 | 0 | 0 | +3.6% |
| 34 | 0.3071 | 0.3006 | 0.4067 | 0.3071 | 0.2878 | 0.3092 | 0 | 0 | +10.7% |
| 36 | 0.3189 | 0.3191 | 0.4358 | 0.3293 | 0.3041 | 0.3171 | 0 | 0 | +15.0% |
| 37 | 0.3344 | 0.3392 | 0.4414 | 0.3431 | 0.3068 | 0.3251 | 0 | 0 | +20.5% |
| 39 | 0.3703 | 0.3679 | 0.4935 | 0.3901 | 0.3242 | 0.3703 | 0 | 0 | +33.5% |

### WR

- Legacy control: **36**
- Prior limited Production V2 comparator: **34**
- Primary 4-week leader: **28**
- Same leader across 2/4/6 weeks: **True**
- Historical screen: **PASS**
- Phase-3 shortlist: **28, 34, 36**

| Rank | Median MAE | Mean MAE | Median RMSE | 2024 MAE | 2025 MAE | Cross MAE | Strict fold wins | Best/tied folds | Δ MAE vs legacy |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 28 | 0.2304 | 0.2194 | 0.3146 | 0.2156 | 0.2384 | 0.1790 | 15 | 15 | -7.3% |
| 32 | 0.2381 | 0.2311 | 0.3244 | 0.2246 | 0.2431 | 0.2053 | 0 | 0 | -4.2% |
| 33 | 0.2396 | 0.2344 | 0.3306 | 0.2348 | 0.2464 | 0.2093 | 0 | 0 | -3.6% |
| 34 | 0.2443 | 0.2374 | 0.3332 | 0.2356 | 0.2495 | 0.2099 | 0 | 0 | -1.7% |
| 36 | 0.2485 | 0.2453 | 0.3457 | 0.2382 | 0.2567 | 0.2228 | 0 | 0 | +0.0% |
| 37 | 0.2536 | 0.2487 | 0.3472 | 0.2387 | 0.2595 | 0.2321 | 0 | 0 | +2.1% |
| 38 | 0.2563 | 0.2539 | 0.3534 | 0.2390 | 0.2630 | 0.2363 | 0 | 0 | +3.1% |
| 40 | 0.2688 | 0.2658 | 0.3662 | 0.2581 | 0.2722 | 0.2419 | 0 | 0 | +8.2% |
| 43 | 0.2826 | 0.2834 | 0.3931 | 0.2745 | 0.2874 | 0.2494 | 0 | 0 | +13.7% |
| 49 | 0.3351 | 0.3328 | 0.4559 | 0.3216 | 0.3394 | 0.2905 | 0 | 0 | +34.8% |

### TE

- Legacy control: **15**
- Prior limited Production V2 comparator: **15**
- Primary 4-week leader: **11**
- Same leader across 2/4/6 weeks: **False**
- Historical screen: **PASS**
- Phase-3 shortlist: **10, 11, 15, 16**

| Rank | Median MAE | Mean MAE | Median RMSE | 2024 MAE | 2025 MAE | Cross MAE | Strict fold wins | Best/tied folds | Δ MAE vs legacy |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 10 | 0.2149 | 0.2167 | 0.3373 | 0.2139 | 0.2149 | 0.2289 | 4 | 4 | -2.9% |
| 11 | 0.2148 | 0.2157 | 0.3364 | 0.2148 | 0.2146 | 0.2286 | 4 | 4 | -2.9% |
| 13 | 0.2195 | 0.2155 | 0.3309 | 0.2195 | 0.2186 | 0.2265 | 1 | 1 | -0.8% |
| 15 | 0.2213 | 0.2168 | 0.3317 | 0.2273 | 0.2168 | 0.2253 | 0 | 1 | +0.0% |
| 16 | 0.2221 | 0.2177 | 0.3299 | 0.2279 | 0.2166 | 0.2250 | 2 | 3 | +0.4% |
| 17 | 0.2231 | 0.2188 | 0.3303 | 0.2318 | 0.2173 | 0.2269 | 2 | 3 | +0.8% |
| 19 | 0.2242 | 0.2225 | 0.3343 | 0.2354 | 0.2192 | 0.2351 | 0 | 0 | +1.3% |
| 20 | 0.2270 | 0.2242 | 0.3373 | 0.2362 | 0.2194 | 0.2354 | 0 | 0 | +2.6% |
| 21 | 0.2318 | 0.2268 | 0.3482 | 0.2370 | 0.2239 | 0.2403 | 1 | 1 | +4.7% |
| 27 | 0.2791 | 0.2901 | 0.4363 | 0.3042 | 0.2791 | 0.2640 | 0 | 0 | +26.1% |
| 33 | 0.3470 | 0.3688 | 0.5463 | 0.3846 | 0.3442 | 0.2921 | 0 | 0 | +56.8% |

### DL

- Legacy control: **32**
- Prior limited Production V2 comparator: **23**
- Primary 4-week leader: **16**
- Same leader across 2/4/6 weeks: **True**
- Historical screen: **PASS**
- Phase-3 shortlist: **16, 23, 32**

| Rank | Median MAE | Mean MAE | Median RMSE | 2024 MAE | 2025 MAE | Cross MAE | Strict fold wins | Best/tied folds | Δ MAE vs legacy |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 16 | 0.1937 | 0.2013 | 0.2693 | 0.2136 | 0.1934 | 0.1807 | 15 | 15 | -24.1% |
| 23 | 0.2280 | 0.2266 | 0.2968 | 0.2338 | 0.2257 | 0.2142 | 0 | 0 | -10.6% |
| 28 | 0.2432 | 0.2431 | 0.3194 | 0.2467 | 0.2432 | 0.2352 | 0 | 0 | -4.7% |
| 29 | 0.2480 | 0.2460 | 0.3254 | 0.2480 | 0.2494 | 0.2385 | 0 | 0 | -2.8% |
| 30 | 0.2492 | 0.2494 | 0.3258 | 0.2492 | 0.2527 | 0.2465 | 0 | 0 | -2.3% |
| 32 | 0.2551 | 0.2555 | 0.3318 | 0.2519 | 0.2561 | 0.2551 | 0 | 0 | +0.0% |
| 34 | 0.2606 | 0.2612 | 0.3338 | 0.2555 | 0.2616 | 0.2606 | 0 | 0 | +2.2% |
| 36 | 0.2654 | 0.2681 | 0.3539 | 0.2665 | 0.2654 | 0.2623 | 0 | 0 | +4.0% |
| 37 | 0.2676 | 0.2700 | 0.3554 | 0.2676 | 0.2695 | 0.2656 | 0 | 0 | +4.9% |
| 39 | 0.2777 | 0.2781 | 0.3598 | 0.2777 | 0.2773 | 0.2807 | 0 | 0 | +8.9% |
| 47 | 0.3198 | 0.3159 | 0.4193 | 0.3112 | 0.3253 | 0.3011 | 0 | 0 | +25.4% |

### LB

- Legacy control: **32**
- Prior limited Production V2 comparator: **32**
- Primary 4-week leader: **28**
- Same leader across 2/4/6 weeks: **True**
- Historical screen: **PASS**
- Phase-3 shortlist: **28, 32**

| Rank | Median MAE | Mean MAE | Median RMSE | 2024 MAE | 2025 MAE | Cross MAE | Strict fold wins | Best/tied folds | Δ MAE vs legacy |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 28 | 0.1883 | 0.1904 | 0.2689 | 0.1873 | 0.1883 | 0.1927 | 15 | 15 | -2.7% |
| 30 | 0.1896 | 0.1932 | 0.2705 | 0.1888 | 0.1896 | 0.1933 | 0 | 0 | -2.1% |
| 32 | 0.1936 | 0.1961 | 0.2781 | 0.1936 | 0.1916 | 0.1949 | 0 | 0 | +0.0% |
| 34 | 0.1962 | 0.1995 | 0.2800 | 0.1962 | 0.1978 | 0.1952 | 0 | 0 | +1.3% |
| 36 | 0.1970 | 0.2017 | 0.2812 | 0.1967 | 0.2014 | 0.1961 | 0 | 0 | +1.8% |
| 40 | 0.2072 | 0.2091 | 0.2892 | 0.2040 | 0.2072 | 0.2073 | 0 | 0 | +7.0% |
| 41 | 0.2078 | 0.2109 | 0.2948 | 0.2042 | 0.2091 | 0.2078 | 0 | 0 | +7.3% |
| 43 | 0.2118 | 0.2166 | 0.2975 | 0.2062 | 0.2136 | 0.2096 | 0 | 0 | +9.4% |
| 50 | 0.2357 | 0.2394 | 0.3285 | 0.2279 | 0.2403 | 0.2357 | 0 | 0 | +21.7% |
| 52 | 0.2475 | 0.2485 | 0.3419 | 0.2386 | 0.2485 | 0.2477 | 0 | 0 | +27.8% |
| 55 | 0.2571 | 0.2608 | 0.3542 | 0.2448 | 0.2603 | 0.2571 | 0 | 0 | +32.8% |

### DB

- Legacy control: **32**
- Prior limited Production V2 comparator: **30**
- Primary 4-week leader: **22**
- Same leader across 2/4/6 weeks: **True**
- Historical screen: **PASS**
- Phase-3 shortlist: **22, 30, 32**

| Rank | Median MAE | Mean MAE | Median RMSE | 2024 MAE | 2025 MAE | Cross MAE | Strict fold wins | Best/tied folds | Δ MAE vs legacy |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 22 | 0.2080 | 0.2072 | 0.2781 | 0.2072 | 0.2106 | 0.2023 | 15 | 15 | -6.6% |
| 28 | 0.2175 | 0.2155 | 0.2900 | 0.2138 | 0.2210 | 0.2077 | 0 | 0 | -2.4% |
| 30 | 0.2219 | 0.2183 | 0.2942 | 0.2160 | 0.2244 | 0.2100 | 0 | 0 | -0.4% |
| 32 | 0.2228 | 0.2207 | 0.3004 | 0.2218 | 0.2265 | 0.2104 | 0 | 0 | +0.0% |
| 34 | 0.2270 | 0.2236 | 0.3033 | 0.2250 | 0.2282 | 0.2121 | 0 | 0 | +1.9% |
| 36 | 0.2311 | 0.2267 | 0.3075 | 0.2300 | 0.2313 | 0.2146 | 0 | 0 | +3.7% |
| 38 | 0.2319 | 0.2291 | 0.3086 | 0.2318 | 0.2334 | 0.2156 | 0 | 0 | +4.1% |
| 40 | 0.2346 | 0.2316 | 0.3134 | 0.2344 | 0.2351 | 0.2179 | 0 | 0 | +5.3% |
| 47 | 0.2440 | 0.2412 | 0.3250 | 0.2440 | 0.2440 | 0.2227 | 0 | 0 | +9.5% |
| 53 | 0.2536 | 0.2495 | 0.3353 | 0.2563 | 0.2517 | 0.2258 | 0 | 0 | +13.8% |

## Guardrails

- deployment_authorized: **false**
- production_v2_change_authorized: **false**
- replacement_rank_change_authorized: **false**
- position_weight_change_authorized: **false**
- scale_change_authorized: **false**
- frozen prospective experiments touched: **false**

## Next step

Phase 3 should run the shortlisted replacement ranks through the current 2026 board while holding Production V2 inputs, age, opportunity, durability, no-history logic, PM transform, position weights, and global scale fixed. That phase measures blast radius and ranking stability; it still does not deploy.
