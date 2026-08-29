# LB Age-Curve Fix — Full Real-Player Impact Audit (2026-08-26)

Every real LB in PLAYER_DB with real production data (73 of 79 — 6 excluded, all for legitimate documented reasons: age beyond range, or no 2026 projection available). Old = linear post-peak decay. New = t^0.5 non-linear decay.


## Affected players (age 30-31 — the only ages that change under integer ages)

| Player | Age | Role | prod_mult | Old AM | New AM | Old Val | New Val | $ Chg | % Chg | Old Rk | New Rk | Rk Chg |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Robert Spillane | 30 | Starter | 0.6689 | 0.8733 | 0.7806 | 3,599 | 3,216 | -383 | -10.6% | 30 | 41 | -11 |
| Tj Edwards | 30 | Starter | 0.6352 | 0.8733 | 0.7806 | 3,417 | 3,054 | -363 | -10.6% | 38 | 46 | -8 |
| Blake Cashman | 30 | Elite | 0.7999 | 0.8733 | 0.7806 | 4,303 | 3,846 | -457 | -10.6% | 15 | 25 | -10 |
| Zaire Franklin | 30 | Starter | 0.6396 | 0.8733 | 0.7806 | 3,441 | 3,076 | -365 | -10.6% | 37 | 43 | -6 |
| Kaden Elliss | 31 | Every-Down | 0.7055 | 0.7467 | 0.6897 | 3,245 | 2,997 | -248 | -7.6% | 44 | 47 | -3 |
| Andrew Van Ginkel | 31 | Rotational | 0.6835 | 0.7467 | 0.6897 | 3,144 | 2,904 | -240 | -7.6% | 45 | 48 | -3 |
| Alex Anzalone | 31 | Rotational | 0.6013 | 0.7467 | 0.6897 | 2,766 | 2,555 | -211 | -7.6% | 51 | 56 | -5 |
| Eric Wilson | 31 | Rotational | 0.6133 | 0.7467 | 0.6897 | 2,821 | 2,606 | -215 | -7.6% | 49 | 53 | -4 |
| Drue Tranquill | 31 | Rotational | 0.6081 | 0.7467 | 0.6897 | 2,797 | 2,584 | -213 | -7.6% | 50 | 54 | -4 |
| Foyesade Oluokun | 31 | Elite | 0.7767 | 0.7467 | 0.6897 | 3,572 | 3,300 | -272 | -7.6% | 33 | 39 | -6 |

## Control group (age 29 & 32 — must show exactly zero change)

| Player | Age | Old Val | New Val | Change |
|---|---|---|---|---|
| Alex Singleton | 32 | 2,568 | 2,568 | +0 |
| Azeez Alshaair | 29 | 3,760 | 3,760 | +0 |
| Christian Rozeboom | 29 | 2,751 | 2,751 | +0 |
| Dre Greenlaw | 29 | 3,061 | 3,061 | +0 |
| Frankie Luvu | 29 | 3,058 | 3,058 | +0 |
| Fred Warner | 29 | 4,630 | 4,630 | +0 |
| Quincy Williams | 29 | 4,023 | 4,023 | +0 |
| Roquan Smith | 29 | 4,663 | 4,663 | +0 |
| Zack Baun | 29 | 4,606 | 4,606 | +0 |

## Full unaffected group (all other ages, 54 players)

Every player outside the 29-32 range shows zero change by construction (pre-peak logic and the shared post-peak formula for other positions are both untouched). Not tabulated individually — confirmed programmatically, not by inspection.
