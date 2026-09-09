# Trade Desk Market Value V1

Method: `league-market-value-v1`  
Scale semantics: `league_rank_quantile_mapped_to_trade_desk_points_v1`  
Policy SHA256: `7d3b6723effd6e3bb7a055e9173cfd5426c7a4457ea924b9e52f3b4de39080cf`

## Critical interpretation

**Market Value is a separate league-opinion lens. It is not the fundamental player-value formula and it is not blended into Team Utility.**

The Bradley–Terry rating scale is arbitrary, so V1 preserves the league-vote ranking and maps that ranking onto the point-value distribution of the exact same covered players. The point number is therefore a comparable market-equivalent scale, while the ordering itself comes from league votes.

- Fundamental model players: **565**
- Market-covered players: **476** (84.2%)
- League votes: **469**
- League pairwise observations: **1407**
- Guest votes excluded: **392**
- Dominant voter share: **59.9%**
- Dominant voter majority flag: **YES**

## Largest current Fundamental ↔ Market disagreements

| Player | Pos | Fundamental | Market | Δ | Market rank | Market pct. | Pos direct pairs |
|---|---|---:|---:|---:|---:|---:|---:|
| jeremiyah love | RB | 4,443 | 8,888 | +4,445 | 1.0 | 100.0% | 26 |
| jahmyr gibbs | RB | 8,888 | 4,522 | -4,366 | 49.0 | 89.9% | 26 |
| nick bolton | LB | 5,351 | 1,426 | -3,925 | 368.0 | 22.7% | 40 |
| ty simpson | QB | 1,169 | 5,086 | +3,917 | 20.0 | 96.0% | 11 |
| drake london | WR | 5,852 | 2,004 | -3,848 | 326.0 | 31.6% | 33 |
| makai lemon | WR | 2,569 | 5,852 | +3,283 | 5.0 | 99.2% | 33 |
| malik davis | RB | 806 | 3,990 | +3,184 | 78.0 | 83.8% | 26 |
| devon achane | RB | 6,673 | 3,501 | -3,172 | 130.0 | 72.8% | 26 |
| devin lloyd | LB | 4,363 | 1,210 | -3,153 | 387.0 | 18.7% | 40 |
| david bailey | DL | 2,374 | 5,493 | +3,119 | 10.0 | 98.1% | 58 |
| nicholas singleton | RB | 1,002 | 3,948 | +2,946 | 85.0 | 82.3% | 26 |
| jaylen waddle | WR | 4,576 | 1,649 | -2,927 | 352.0 | 26.1% | 33 |
| kyle louis | LB | 968 | 3,862 | +2,894 | 90.0 | 81.3% | 40 |
| max klare | TE | 780 | 3,644 | +2,864 | 109.0 | 77.3% | 6 |
| trevon moehrig | DB | 3,636 | 774 | -2,862 | 459.0 | 3.6% | 49 |
| jonah coleman | RB | 1,126 | 3,984 | +2,858 | 79.0 | 83.6% | 26 |
| tucker kraft | TE | 3,739 | 6,564 | +2,825 | 3.0 | 99.6% | 6 |
| dj giddens | RB | 734 | 3,558 | +2,824 | 123.0 | 74.3% | 26 |
| zach ertz | TE | 805 | 3,625 | +2,820 | 112.0 | 76.6% | 6 |
| jake golday | LB | 1,162 | 3,980 | +2,818 | 80.0 | 83.4% | 40 |
| cj allen | LB | 2,021 | 4,820 | +2,799 | 31.0 | 93.7% | 40 |
| fernando mendoza | QB | 2,150 | 4,912 | +2,762 | 27.0 | 94.5% | 11 |
| austin booker | DL | 3,431 | 670 | -2,761 | 469.0 | 1.5% | 58 |
| cyrus allen | WR | 1,037 | 3,784 | +2,747 | 96.0 | 80.0% | 33 |
| devin singletary | RB | 687 | 3,416 | +2,729 | 141.0 | 70.5% | 26 |
| jameson williams | WR | 4,829 | 2,150 | -2,679 | 311.0 | 34.7% | 33 |
| montez sweat | DL | 3,948 | 1,282 | -2,666 | 383.0 | 19.6% | 58 |
| xavier watts | DB | 3,416 | 770 | -2,646 | 460.0 | 3.4% | 49 |
| kaelon black | RB | 896 | 3,539 | +2,643 | 125.0 | 73.9% | 26 |
| divine deablo | LB | 3,501 | 882 | -2,619 | 441.0 | 7.4% | 40 |

## Guardrails

- `league_only.player_ratings` is the only market ordering source.
- Guest votes are not blended into Market Value V1.
- A market value never changes the deployed fundamental value.
- Team Utility remains a separate roster-specific calculation.
- Unrated players have no Market Value V1 rather than receiving an invented estimate.
- Voter concentration and direct positional sample size are carried with the output.
