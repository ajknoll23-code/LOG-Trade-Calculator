# Trade Desk Market Value V1

Method: `league-market-value-v1`  
Scale semantics: `league_rank_quantile_mapped_to_trade_desk_points_v1`  
Policy SHA256: `7d3b6723effd6e3bb7a055e9173cfd5426c7a4457ea924b9e52f3b4de39080cf`

## Critical interpretation

**Market Value is a separate league-opinion lens. It is not the fundamental player-value formula and it is not blended into Team Utility.**

The Bradley–Terry rating scale is arbitrary, so V1 preserves the league-vote ranking and maps that ranking onto the point-value distribution of the exact same covered players. The point number is therefore a comparable market-equivalent scale, while the ordering itself comes from league votes.

- Fundamental model players: **565**
- Market-covered players: **463** (82.0%)
- League votes: **414**
- League pairwise observations: **1242**
- Guest votes excluded: **20**
- Dominant voter share: **63.0%**
- Dominant voter majority flag: **YES**

## Largest current Fundamental ↔ Market disagreements

| Player | Pos | Fundamental | Market | Δ | Market rank | Market pct. | Pos direct pairs |
|---|---|---:|---:|---:|---:|---:|---:|
| jahmyr gibbs | RB | 8,902 | 4,604 | -4,298 | 42.0 | 91.1% | 25 |
| ty simpson | QB | 1,169 | 5,401 | +4,232 | 13.0 | 97.4% | 8 |
| nick bolton | LB | 5,351 | 1,150 | -4,201 | 385.0 | 16.9% | 33 |
| david bailey | DL | 2,374 | 6,564 | +4,190 | 3.0 | 99.6% | 50 |
| drake london | WR | 5,852 | 1,696 | -4,156 | 338.0 | 27.1% | 31 |
| trey mcbride | TE | 5,087 | 8,902 | +3,815 | 1.0 | 100.0% | 5 |
| bhayshul tuten | RB | 3,157 | 6,684 | +3,527 | 2.0 | 99.8% | 25 |
| devon achane | RB | 6,684 | 3,453 | -3,231 | 129.0 | 72.3% | 25 |
| malik davis | RB | 807 | 3,991 | +3,184 | 72.0 | 84.6% | 25 |
| dorian williams | LB | 2,297 | 5,445 | +3,148 | 12.0 | 97.6% | 33 |
| devin lloyd | LB | 4,363 | 1,303 | -3,060 | 369.0 | 20.3% | 33 |
| jaylen waddle | WR | 4,576 | 1,556 | -3,020 | 347.0 | 25.1% | 31 |
| kyle louis | LB | 968 | 3,968 | +3,000 | 78.0 | 83.3% | 33 |
| jake golday | LB | 1,162 | 4,156 | +2,994 | 63.0 | 86.6% | 33 |
| chris olave | WR | 5,445 | 2,456 | -2,989 | 268.0 | 42.2% | 31 |
| nicholas singleton | RB | 1,000 | 3,984 | +2,984 | 74.0 | 84.2% | 25 |
| max klare | TE | 780 | 3,739 | +2,959 | 98.0 | 79.0% | 5 |
| jonah coleman | RB | 1,126 | 4,050 | +2,924 | 71.0 | 84.8% | 25 |
| zach ertz | TE | 805 | 3,711 | +2,906 | 100.0 | 78.6% | 5 |
| dj giddens | RB | 734 | 3,618 | +2,884 | 109.0 | 76.6% | 25 |
| brian burns | DL | 5,623 | 2,794 | -2,829 | 217.0 | 53.2% | 50 |
| cyrus allen | WR | 1,037 | 3,859 | +2,822 | 85.5 | 81.7% | 31 |
| trevon moehrig | DB | 3,636 | 827 | -2,809 | 435.0 | 6.1% | 45 |
| tj hockenson | TE | 2,305 | 5,086 | +2,781 | 19.0 | 96.1% | 5 |
| rueben bain | DL | 2,026 | 4,796 | +2,770 | 30.0 | 93.7% | 50 |
| austin booker | DL | 3,431 | 668 | -2,763 | 457.0 | 1.3% | 50 |
| jameson williams | WR | 4,829 | 2,079 | -2,750 | 307.0 | 33.8% | 31 |
| devin singletary | RB | 687 | 3,416 | +2,729 | 135.0 | 71.0% | 25 |
| kaelon black | RB | 896 | 3,611 | +2,715 | 110.0 | 76.4% | 25 |
| kyle hamilton | DB | 3,791 | 1,077 | -2,714 | 395.5 | 14.6% | 45 |

## Guardrails

- `league_only.player_ratings` is the only market ordering source.
- Guest votes are not blended into Market Value V1.
- A market value never changes the deployed fundamental value.
- Team Utility remains a separate roster-specific calculation.
- Unrated players have no Market Value V1 rather than receiving an invented estimate.
- Voter concentration and direct positional sample size are carried with the output.
