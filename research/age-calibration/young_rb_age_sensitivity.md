# Young RB Age Sensitivity Audit

**Status:** research-only; no production values changed.

## Audit question

How much can the current elite-young-RB age premium move real Fundamental Values, RB ranks, and one-year age transitions before we decide whether the curve should be recalibrated?

## Live rule being audited

```text
position = RB
role = Elite
age <= 25
raw PROD_MULT_DATA >= 0.65
youth_bonus = 0.384 × sqrt(peakEnd - age)
```

- Current young RBs age 21-25: **59**
- Current premium qualifiers: **5**
- Young RBs with Market Value context: **45**

## Current young-RB cohort

| Player | Age | Role | Raw PM | Age mult | Fundamental | RB rank | Premium? | Market |
|---|---:|---|---:|---:|---:|---:|---|---:|
| bijan robinson | 24 | Elite | 1.550 | 1.384 | 10501 | 1 | yes | n/a |
| jahmyr gibbs | 24 | Elite | 1.550 | 1.384 | 10501 | 2 | yes | 4604 |
| devon achane | 24 | Elite | 1.323 | 1.384 | 8963 | 3 | yes | 3520 |
| ashton jeanty | 22 | Elite | 1.089 | 1.390 | 7410 | 4 | yes | n/a |
| kyren williams | 25 | Elite | 1.098 | 1.000 | 5375 | 7 | yes | 5401 |
| kenneth walker | 25 | Every-Down | 1.056 | 1.000 | 5169 | 9 | no | 4347 |
| breece hall | 25 | Every-Down | 1.040 | 1.000 | 5091 | 10 | no | 3286 |
| omarion hampton | 23 | Every-Down | 1.039 | 1.000 | 5086 | 11 | no | 4522 |
| cam skattebo | 24 | Every-Down | 0.994 | 1.000 | 4866 | 13 | no | n/a |
| bucky irving | 23 | Every-Down | 0.933 | 1.000 | 4567 | 15 | no | n/a |
| jeremiyah love | 21 | Every-Down | 1.063 | 0.830 | 4321 | 16 | no | 5351 |
| quinshon judkins | 22 | Every-Down | 0.898 | 0.890 | 3912 | 21 | no | n/a |
| treveyon henderson | 23 | Starter | 0.773 | 1.000 | 3784 | 24 | no | 4796 |
| rj harvey | 25 | Starter | 0.739 | 1.000 | 3617 | 25 | no | 4428 |
| bhayshul tuten | 24 | Rotational | 0.645 | 1.000 | 3157 | 27 | no | 4765 |
| jadarian price | 22 | Starter | 0.742 | 0.866 | 3145 | 28 | no | 3775 |
| kyle monangai | 24 | Rotational | 0.629 | 1.000 | 3079 | 30 | no | 4169 |
| blake corum | 25 | Rotational | 0.609 | 1.000 | 2981 | 31 | no | 3984 |
| woody marks | 25 | Rotational | 0.566 | 1.000 | 2771 | 36 | no | 2776 |
| jacory croskeymerritt | 25 | Rotational | 0.564 | 1.000 | 2761 | 37 | no | 2803 |
| zach charbonnet | 25 | Rotational | 0.555 | 1.000 | 2717 | 39 | no | 2579 |
| jonathon brooks | 23 | Rotational | 0.516 | 1.000 | 2526 | 43 | no | 4195 |
| tyjae spears | 25 | Understudy | 0.469 | 1.000 | 2296 | 45 | no | 1645 |
| kimani vidal | 24 | Understudy | 0.398 | 1.000 | 1948 | 47 | no | 1029 |
| keaton mitchell | 24 | Depth | 0.288 | 1.000 | 1410 | 51 | no | n/a |
| phil mafah | 23 | Depth | 0.262 | 1.000 | 1282 | 52 | no | 1079 |
| sean tucker | 24 | Depth | 0.260 | 1.000 | 1273 | 53 | no | n/a |
| tank bigsby | 23 | Depth | 0.243 | 1.000 | 1189 | 55 | no | 1162 |
| dylan sampson | 21 | Understudy | 0.380 | 0.621 | 1154 | 56 | no | 1073 |
| isaiah davis | 24 | Depth | 0.228 | 1.000 | 1116 | 58 | no | 2558 |
| trey benson | 24 | Depth | 0.227 | 1.000 | 1111 | 59 | no | 754 |
| bam knight | 25 | Speculative | 0.150 | 1.000 | 1077 | 61 | no | 1631 |
| donovan edwards | 23 | Speculative | 0.150 | 1.000 | 1077 | 62 | no | n/a |
| eli heidenreich | 23 | Speculative | 0.150 | 1.000 | 1077 | 63 | no | 2499 |
| jmari taylor | 24 | Speculative | 0.150 | 1.000 | 1077 | 64 | no | n/a |
| kaytron allen | 23 | Speculative | 0.150 | 1.000 | 1077 | 65 | no | 3306 |
| leveon moss | 23 | Speculative | 0.150 | 1.000 | 1077 | 66 | no | 1162 |
| seth mcgowan | 24 | Speculative | 0.150 | 1.000 | 1077 | 67 | no | n/a |
| braelon allen | 22 | Depth | 0.263 | 0.792 | 1020 | 68 | no | 3216 |
| marshawn lloyd | 25 | Speculative | 0.195 | 1.000 | 955 | 69 | no | 2726 |
| kaelon black | 24 | Speculative | 0.183 | 1.000 | 896 | 70 | no | 3585 |
| jonah coleman | 22 | Depth | 0.230 | 0.787 | 886 | 72 | no | 4096 |
| adam randall | 22 | Speculative | 0.150 | 0.786 | 846 | 75 | no | 1176 |
| demond claiborne | 22 | Speculative | 0.150 | 0.786 | 846 | 76 | no | 2785 |
| emmett johnson | 22 | Speculative | 0.150 | 0.786 | 846 | 77 | no | 3340 |
| jam miller | 22 | Speculative | 0.150 | 0.786 | 846 | 78 | no | n/a |
| nicholas singleton | 22 | Speculative | 0.150 | 0.786 | 846 | 79 | no | 3991 |
| mike washington | 23 | Speculative | 0.172 | 1.000 | 842 | 80 | no | 2567 |
| devin neal | 23 | Speculative | 0.163 | 1.000 | 798 | 81 | no | 2841 |
| jaydon blue | 22 | Depth | 0.203 | 0.783 | 778 | 82 | no | 2574 |
| audric estime | 22 | Speculative | 0.197 | 0.782 | 754 | 84 | no | 1375 |
| brashard smith | 23 | Speculative | 0.150 | 1.000 | 734 | 85 | no | 2346 |
| kaleb johnson | 23 | Speculative | 0.150 | 1.000 | 734 | 86 | no | 2460 |
| kendre miller | 24 | Speculative | 0.150 | 1.000 | 734 | 87 | no | n/a |
| tahj brooks | 24 | Speculative | 0.150 | 1.000 | 734 | 88 | no | 2752 |
| jordan james | 22 | Speculative | 0.179 | 0.779 | 683 | 90 | no | 680 |
| ollie gordon | 22 | Speculative | 0.166 | 0.777 | 632 | 95 | no | n/a |
| dj giddens | 22 | Speculative | 0.150 | 0.775 | 569 | 96 | no | 3618 |
| lequint allen | 22 | Speculative | 0.150 | 0.775 | 569 | 97 | no | n/a |

## Coefficient sensitivity

Every scenario keeps position, production, role, and every non-age model input fixed.

| Coefficient | N | Median abs move | P90 abs move | Max abs move | Median abs % | P90 abs % | Max abs % | Max RB-rank move |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.000 | 5 | 2914.0 | 3292.6 | 3545.0 | +27.7% | +39.8% | +47.8% | 17 |
| 0.250 | 5 | 1017.0 | 1149.0 | 1237.0 | +9.7% | +13.9% | +16.7% | 2 |
| 0.300 | 5 | 638.0 | 720.2 | 775.0 | +6.1% | +8.7% | +10.5% | 0 |
| 0.340 | 5 | 334.0 | 377.2 | 406.0 | +3.2% | +4.6% | +5.5% | 0 |
| 0.384 | 5 | 0.0 | 0.0 | 0.0 | +0.0% | +0.0% | +0.0% | 0 |
| 0.430 | 5 | 349.0 | 394.6 | 425.0 | +3.3% | +4.8% | +5.7% | 0 |
| 0.480 | 5 | 622.0 | 728.0 | 728.0 | +6.9% | +7.5% | +7.9% | 0 |

### Largest movers with the youth premium removed

| Player | Age | Current | No premium | Delta | Delta % | RB rank now | RB rank no premium | Market |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| ashton jeanty | 22 | 7410 | 3865 | -3545 | -47.8% | 4 | 21 | n/a |
| bijan robinson | 24 | 10501 | 7587 | -2914 | -27.7% | 1 | 1 | n/a |
| jahmyr gibbs | 24 | 10501 | 7587 | -2914 | -27.7% | 2 | 2 | 4604 |
| devon achane | 24 | 8963 | 6476 | -2487 | -27.7% | 3 | 4 | 3520 |
| kyren williams | 25 | 5375 | 5375 | +0 | +0.0% | 7 | 6 | 5401 |

## One-year aging shock under the CURRENT formula

Production and role are held fixed; only age changes by +1.

| Player | Age → Age+1 | Age mult now | Age mult +1 | Value now | Value +1 | Delta | Delta % |
|---|---|---:|---:|---:|---:|---:|---:|
| dylan sampson | 21 → 22 | 0.621 | 0.810 | 1154 | 1507 | +353 | +30.6% |
| dj giddens | 22 → 23 | 0.775 | 1.000 | 569 | 734 | +165 | +29.0% |
| lequint allen | 22 → 23 | 0.775 | 1.000 | 569 | 734 | +165 | +29.0% |
| ollie gordon | 22 → 23 | 0.777 | 1.000 | 632 | 813 | +181 | +28.6% |
| jordan james | 22 → 23 | 0.779 | 1.000 | 683 | 876 | +193 | +28.3% |
| audric estime | 22 → 23 | 0.782 | 1.000 | 754 | 964 | +210 | +27.9% |
| jaydon blue | 22 → 23 | 0.783 | 1.000 | 778 | 994 | +216 | +27.8% |
| bijan robinson | 24 → 25 | 1.384 | 1.000 | 10501 | 7587 | -2914 | -27.7% |
| jahmyr gibbs | 24 → 25 | 1.384 | 1.000 | 10501 | 7587 | -2914 | -27.7% |
| devon achane | 24 → 25 | 1.384 | 1.000 | 8963 | 6476 | -2487 | -27.7% |
| adam randall | 22 → 23 | 0.786 | 1.000 | 846 | 1077 | +231 | +27.3% |
| demond claiborne | 22 → 23 | 0.786 | 1.000 | 846 | 1077 | +231 | +27.3% |
| emmett johnson | 22 → 23 | 0.786 | 1.000 | 846 | 1077 | +231 | +27.3% |
| jam miller | 22 → 23 | 0.786 | 1.000 | 846 | 1077 | +231 | +27.3% |
| nicholas singleton | 22 → 23 | 0.786 | 1.000 | 846 | 1077 | +231 | +27.3% |
| jonah coleman | 22 → 23 | 0.787 | 1.000 | 886 | 1126 | +240 | +27.1% |
| braelon allen | 22 → 23 | 0.792 | 1.000 | 1020 | 1287 | +267 | +26.2% |
| jadarian price | 22 → 23 | 0.866 | 1.000 | 3145 | 3632 | +487 | +15.5% |
| quinshon judkins | 22 → 23 | 0.890 | 1.000 | 3912 | 4396 | +484 | +12.4% |
| jeremiyah love | 21 → 22 | 0.830 | 0.915 | 4321 | 4762 | +441 | +10.2% |
| ashton jeanty | 22 → 23 | 1.390 | 1.268 | 7410 | 6760 | -650 | -8.8% |
| marshawn lloyd | 25 → 26 | 1.000 | 0.924 | 955 | 882 | -73 | -7.6% |
| tyjae spears | 25 → 26 | 1.000 | 0.924 | 2296 | 2121 | -175 | -7.6% |
| zach charbonnet | 25 → 26 | 1.000 | 0.924 | 2717 | 2510 | -207 | -7.6% |
| blake corum | 25 → 26 | 1.000 | 0.924 | 2981 | 2754 | -227 | -7.6% |
| woody marks | 25 → 26 | 1.000 | 0.924 | 2771 | 2560 | -211 | -7.6% |
| bam knight | 25 → 26 | 1.000 | 0.924 | 1077 | 995 | -82 | -7.6% |
| kyren williams | 25 → 26 | 1.000 | 0.924 | 5375 | 4966 | -409 | -7.6% |
| jacory croskeymerritt | 25 → 26 | 1.000 | 0.924 | 2761 | 2551 | -210 | -7.6% |
| kenneth walker | 25 → 26 | 1.000 | 0.924 | 5169 | 4776 | -393 | -7.6% |

## Interpretation boundary

This measures **leverage, not truth**. Large movement proves the age assumption is consequential; it does not prove a different coefficient is more accurate.

