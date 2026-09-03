# KTC Voter-Cap Sensitivity Analysis

Method: `ktc-voter-cap-sensitivity-v1`  
Source KTC generated at: `2026-09-03T14:40:13.737692`  
League votes: **379**  
Status: `research_only_no_market_value_change`

## Result

Near-cap-30 sensitivity: **`low_near_cap30`**

This asks a narrow question: if the effective lifetime cap were 20, 40, 60, 90, or 120 instead of 30, would the league ordering stay broadly the same?

## Cap comparison

| Cap | Capped voters | Effective votes | Largest voter | Eff. voter count | Spearman vs 30 | Median |Δ rank| | Top-20 overlap vs 30 |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 20 | 3 | 117.0 | 17.09% | 6.623 | 0.99474 | 5.0 | 16/20 (80.0%) |
| 30 | 2 | 143.0 | 20.98% | 6.117 | 1.0 | 0.0 | 20/20 (100.0%) |
| 40 | 1 | 159.0 | 25.16% | 5.695 | 0.997872 | 3.0 | 16/20 (80.0%) |
| 60 | 1 | 179.0 | 33.52% | 4.976 | 0.98987 | 8.0 | 16/20 (80.0%) |
| 90 | 1 | 209.0 | 43.06% | 3.993 | 0.967698 | 14.0 | 15/20 (75.0%) |
| 120 | 1 | 239.0 | 50.21% | 3.313 | 0.944253 | 19.0 | 15/20 (75.0%) |

## Reference checks

- Uncapped raw vs cap-30 Spearman: **0.854026**
- Uncapped raw vs cap-30 top-20 overlap: **10/20 (50.0%)**
- Recomputed cap-30 vs stored KTC cap-30 Spearman: **0.999999**

## Top 20 by cap

### Cap 20

1. dorian williams
2. travis etienne
3. carnell tate
4. george karlaftis
5. rome odunze
6. micah parsons
7. yaya diaby
8. aidan hutchinson
9. fred warner
10. alontae taylor
11. drue tranquill
12. emeka egbuka
13. tyler shough
14. lamar jackson
15. abdul carter
16. bradley chubb
17. ty simpson
18. trey mcbride
19. kyren williams
20. kenyon sadiq

### Cap 30

1. dorian williams
2. travis etienne
3. carnell tate
4. yaya diaby
5. george karlaftis
6. alontae taylor
7. rome odunze
8. tyler shough
9. micah parsons
10. aidan hutchinson
11. ty simpson
12. trey mcbride
13. emeka egbuka
14. fred warner
15. drue tranquill
16. will anderson
17. lamar jackson
18. tj watt
19. carson schwesinger
20. terry mclaurin

### Cap 40

1. dorian williams
2. travis etienne
3. rome odunze
4. yaya diaby
5. george karlaftis
6. tyler shough
7. carnell tate
8. alontae taylor
9. micah parsons
10. will anderson
11. aidan hutchinson
12. ty simpson
13. trey mcbride
14. terry mclaurin
15. brock bowers
16. nick emmanwori
17. harold fannin
18. emeka egbuka
19. c schwesinger
20. fred warner

### Cap 60

1. dorian williams
2. travis etienne
3. rome odunze
4. tyler shough
5. carnell tate
6. george karlaftis
7. alontae taylor
8. yaya diaby
9. micah parsons
10. trey mcbride
11. brock bowers
12. ty simpson
13. nick emmanwori
14. harold fannin
15. aidan hutchinson
16. emeka egbuka
17. c schwesinger
18. will anderson
19. terry mclaurin
20. carson schwesinger

### Cap 90

1. rome odunze
2. tyler shough
3. travis etienne
4. dorian williams
5. carnell tate
6. micah parsons
7. alontae taylor
8. george karlaftis
9. trey mcbride
10. brock bowers
11. nick emmanwori
12. yaya diaby
13. ty simpson
14. harold fannin
15. c schwesinger
16. emeka egbuka
17. carson schwesinger
18. aidan hutchinson
19. tj watt
20. jeremiyah love

### Cap 120

1. rome odunze
2. tyler shough
3. travis etienne
4. trey mcbride
5. nick emmanwori
6. carnell tate
7. micah parsons
8. brock bowers
9. dorian williams
10. ty simpson
11. harold fannin
12. alontae taylor
13. george karlaftis
14. c schwesinger
15. carson schwesinger
16. emeka egbuka
17. yaya diaby
18. tj watt
19. aidan hutchinson
20. jeremiyah love

## Decision guardrail

Keep Market Value V1 on league_only until repeated snapshots show that a voter-balance policy is stable and prospectively more representative/predictive.

The sensitivity label is **not** permission to switch Market Value. A cap can be internally stable and still be the wrong market estimator. We need repeated snapshots and prospective evidence before promotion.
