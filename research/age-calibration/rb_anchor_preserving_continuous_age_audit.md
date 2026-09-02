# RB Anchor-Preserving Continuous Age Audit

**Status:** research-only; no production values changed.

## Elite anchor example

| Candidate | 21 | 22 | 23 | 24 | 25 | 26 |
|---|---:|---:|---:|---:|---:|---:|
| continuous_current_anchors | 1.493 | 1.390 | 1.268 | 1.384 | 1.000 | 0.924 |
| continuous_monotone_elite_anchors | 1.493 | 1.390 | 1.326 | 1.326 | 1.000 | 0.924 |

## Birthday-event error

| Cohort | N | Candidate | MAE | Median abs error | Median bias |
|---|---:|---|---:|---:|---:|
| all | 48 | deployed_integer | +21.9% | +16.4% | +8.9% |
| all | 48 | continuous_current_anchors | +22.1% | +17.7% | +2.4% |
| all | 48 | continuous_monotone_elite_anchors | +22.1% | +17.7% | +2.4% |
| meaningful_pm | 26 | deployed_integer | +17.6% | +13.3% | +8.9% |
| meaningful_pm | 26 | continuous_current_anchors | +16.2% | +11.7% | +1.9% |
| meaningful_pm | 26 | continuous_monotone_elite_anchors | +16.3% | +11.7% | +1.9% |
| high_pm | 15 | deployed_integer | +15.5% | +9.5% | +4.3% |
| high_pm | 15 | continuous_current_anchors | +12.0% | +4.1% | +1.2% |
| high_pm | 15 | continuous_monotone_elite_anchors | +12.0% | +4.1% | +1.2% |
| elite | 6 | deployed_integer | +17.5% | +8.9% | -1.3% |
| elite | 6 | continuous_current_anchors | +15.8% | +5.4% | -1.2% |
| elite | 6 | continuous_monotone_elite_anchors | +16.0% | +5.6% | -1.4% |

## Current-board blast radius

| Candidate | Changed | Median abs pts | P90 abs pts | Max abs pts | Median abs % | P90 abs % | Max abs % | Valuable median abs % | Valuable max abs % | >=10% | >=20% | Max 1-day age move |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| continuous_current_anchors | 62/90 | 72 | 343 | 2208 | +4.1% | +17.9% | +29.6% | +5.4% | +24.6% | 16 | 7 | +0.1% |
| continuous_monotone_elite_anchors | 62/90 | 72 | 292 | 2250 | +3.9% | +18.0% | +29.6% | +4.4% | +25.1% | 16 | 7 | +0.1% |

## Largest movers — continuous_current_anchors

| Player | Fractional age | Role | Current | Candidate | Delta | Delta % | Current RB rank | Candidate RB rank | Rank move |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|
| devon achane | 24.89 | Elite | 8963 | 6755 | -2208 | -24.6% | 3 | 4 | -1 |
| bijan robinson | 24.59 | Elite | 10501 | 8785 | -1716 | -16.3% | 1 | 2 | -1 |
| jahmyr gibbs | 24.45 | Elite | 10501 | 9176 | -1325 | -12.6% | 2 | 1 | +1 |
| james cook | 26.94 | Elite | 6495 | 5994 | -501 | -7.7% | 5 | 5 | +0 |
| ashton jeanty | 22.75 | Elite | 7410 | 6922 | -488 | -6.6% | 4 | 3 | +1 |
| jadarian price | 22.90 | Starter | 3145 | 3583 | +438 | +13.9% | 28 | 23 | +5 |
| kyren williams | 26.02 | Elite | 5375 | 4958 | -417 | -7.8% | 7 | 11 | -4 |
| quinshon judkins | 22.84 | Every-Down | 3912 | 4320 | +408 | +10.4% | 21 | 17 | +4 |
| jonathan taylor | 27.62 | Elite | 6276 | 5928 | -348 | -5.5% | 6 | 6 | +0 |
| dylan sampson | 21.97 | Understudy | 1154 | 1496 | +342 | +29.6% | 56 | 50 | +6 |
| jaylen warren | 27.84 | Every-Down | 3819 | 3533 | -286 | -7.5% | 22 | 25 | -3 |
| jonah coleman | 23.04 | Depth | 886 | 1126 | +240 | +27.1% | 72 | 58 | +14 |
| saquon barkley | 29.56 | Elite | 3799 | 3566 | -233 | -6.1% | 23 | 24 | -1 |
| dandre swift | 27.63 | Every-Down | 4093 | 3861 | -232 | -5.7% | 19 | 21 | -2 |
| travis etienne | 27.60 | Every-Down | 4300 | 4069 | -231 | -5.4% | 17 | 18 | -1 |
| josh jacobs | 28.56 | Elite | 4195 | 3965 | -230 | -5.5% | 18 | 19 | -1 |
| audric estime | 22.99 | Speculative | 754 | 962 | +208 | +27.6% | 84 | 73 | +11 |
| chris rodriguez | 26.93 | Rotational | 2705 | 2497 | -208 | -7.7% | 40 | 42 | -2 |
| demond claiborne | 22.90 | Speculative | 846 | 1054 | +208 | +24.6% | 76 | 68 | +8 |
| emmett johnson | 22.90 | Speculative | 846 | 1053 | +207 | +24.5% | 77 | 69 | +8 |
| chase brown | 26.45 | Elite | 5328 | 5130 | -198 | -3.7% | 8 | 8 | +0 |
| jk dobbins | 27.71 | Starter | 3097 | 2900 | -197 | -6.4% | 29 | 30 | -1 |
| tyrone tracy | 26.78 | Rotational | 2782 | 2604 | -178 | -6.4% | 35 | 38 | -3 |
| blake corum | 25.77 | Rotational | 2981 | 2807 | -174 | -5.8% | 31 | 32 | -1 |
| braelon allen | 22.62 | Depth | 1020 | 1185 | +165 | +16.2% | 68 | 57 | +11 |

## Largest movers — continuous_monotone_elite_anchors

| Player | Fractional age | Role | Current | Candidate | Delta | Delta % | Current RB rank | Candidate RB rank | Rank move |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|
| devon achane | 24.89 | Elite | 8963 | 6713 | -2250 | -25.1% | 3 | 4 | -1 |
| bijan robinson | 24.59 | Elite | 10501 | 8604 | -1897 | -18.1% | 1 | 2 | -1 |
| jahmyr gibbs | 24.45 | Elite | 10501 | 8936 | -1565 | -14.9% | 2 | 1 | +1 |
| james cook | 26.94 | Elite | 6495 | 5994 | -501 | -7.7% | 5 | 5 | +0 |
| jadarian price | 22.90 | Starter | 3145 | 3583 | +438 | +13.9% | 28 | 23 | +5 |
| kyren williams | 26.02 | Elite | 5375 | 4958 | -417 | -7.8% | 7 | 11 | -4 |
| quinshon judkins | 22.84 | Every-Down | 3912 | 4320 | +408 | +10.4% | 21 | 17 | +4 |
| jonathan taylor | 27.62 | Elite | 6276 | 5928 | -348 | -5.5% | 6 | 6 | +0 |
| dylan sampson | 21.97 | Understudy | 1154 | 1496 | +342 | +29.6% | 56 | 50 | +6 |
| jaylen warren | 27.84 | Every-Down | 3819 | 3533 | -286 | -7.5% | 22 | 25 | -3 |
| ashton jeanty | 22.75 | Elite | 7410 | 7154 | -256 | -3.5% | 4 | 3 | +1 |
| jonah coleman | 23.04 | Depth | 886 | 1126 | +240 | +27.1% | 72 | 58 | +14 |
| saquon barkley | 29.56 | Elite | 3799 | 3566 | -233 | -6.1% | 23 | 24 | -1 |
| dandre swift | 27.63 | Every-Down | 4093 | 3861 | -232 | -5.7% | 19 | 21 | -2 |
| travis etienne | 27.60 | Every-Down | 4300 | 4069 | -231 | -5.4% | 17 | 18 | -1 |
| josh jacobs | 28.56 | Elite | 4195 | 3965 | -230 | -5.5% | 18 | 19 | -1 |
| audric estime | 22.99 | Speculative | 754 | 962 | +208 | +27.6% | 84 | 73 | +11 |
| chris rodriguez | 26.93 | Rotational | 2705 | 2497 | -208 | -7.7% | 40 | 42 | -2 |
| demond claiborne | 22.90 | Speculative | 846 | 1054 | +208 | +24.6% | 76 | 68 | +8 |
| emmett johnson | 22.90 | Speculative | 846 | 1053 | +207 | +24.5% | 77 | 69 | +8 |
| chase brown | 26.45 | Elite | 5328 | 5130 | -198 | -3.7% | 8 | 8 | +0 |
| jk dobbins | 27.71 | Starter | 3097 | 2900 | -197 | -6.4% | 29 | 30 | -1 |
| tyrone tracy | 26.78 | Rotational | 2782 | 2604 | -178 | -6.4% | 35 | 38 | -3 |
| blake corum | 25.77 | Rotational | 2981 | 2807 | -174 | -5.8% | 31 | 32 | -1 |
| braelon allen | 22.62 | Depth | 1020 | 1185 | +165 | +16.2% | 68 | 57 | +11 |

## Decision rule

Prefer anchor-preserving continuity if it removes birthday discontinuities and keeps the external-event improvement seen with fractional age while materially reducing the live-board repricing versus the earlier age-21-to-25 taper candidates.
