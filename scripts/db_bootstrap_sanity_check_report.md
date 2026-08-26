# DB Bootstrap Sanity Check

```
DB: 30 distinct (season, week) blocks, 1475 roster observations total.

Check 1 -- full dataset, direct bin_curve/crossing_rank path: DB 50%-crossing = 40  (expected: 40)
Check 2 -- identity resample (every block exactly once) through the same bin_curve/crossing_rank call: DB 50%-crossing = 40  (expected: 40)

Check 1 and Check 2 agree with each other AND with the originally reported DB40 -- the direct/no-resampling code path is internally consistent.

Check 3 -- distribution of 200 real bootstrap crossings:
  n resolved: 200/200
  min=22  max=43  median=28
  histogram (rank bucket: count, bar):
     20-29 :  116  ####################################################################################################################
     30-39 :   34  ##################################
     40-49 :   50  ##################################################

For reference, bootstrap_crossing()'s own summary: median=28 p10=22 p90=40 (200/200 resolved)
```
