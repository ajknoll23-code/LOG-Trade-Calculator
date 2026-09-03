# FantasyPros ↔ Sleeper Unified Identity Report

Production resolver covering QB / RB / WR / TE / DL / LB / DB.

- FantasyPros tracked rows: **1034**
- Authoritative stable-ID matches: **923**
- Manual-review rows: **16**

## Coverage by position

| Pos | FP rows | Authoritative | Match rate | Candidate | Manual review |
|---|---:|---:|---:|---:|---:|
| QB | 79 | 70 | 88.6% | 73 | 3 |
| RB | 119 | 108 | 90.8% | 108 | 0 |
| WR | 179 | 161 | 89.9% | 162 | 1 |
| TE | 118 | 110 | 93.2% | 113 | 3 |
| DL | 177 | 158 | 89.3% | 160 | 2 |
| LB | 159 | 141 | 88.7% | 143 | 6 |
| DB | 203 | 175 | 86.2% | 175 | 1 |

## Match methods

- `name_collision_resolved_by_position_team`: **4**
- `name_found_position_incompatible`: **5**
- `name_position_team_confirmed`: **919**
- `no_sleeper_name_candidate`: **95**
- `unique_name_position_team_unavailable`: **11**

## Manual-review rows

These remain deliberately unresolved; downstream consumers must use existing fallback behavior rather than guess identity.

| Player | Pos | FP team | Candidate SID | Sleeper team | Method |
|---|---|---|---|---|---|
| Brady Cook | QB |  | 12538 |  | unique_name_position_team_unavailable |
| Jake Browning | QB |  | 6111 |  | unique_name_position_team_unavailable |
| Desmond Ridder | QB |  | 8159 |  | unique_name_position_team_unavailable |
| Xavier Weaver | WR |  | 11921 |  | unique_name_position_team_unavailable |
| Justin Joly | TE |  | 13400 |  | unique_name_position_team_unavailable |
| Jack Stoll | TE |  | 7946 |  | unique_name_position_team_unavailable |
| Devin Culp | TE |  | 11820 | TB | unique_name_position_team_unavailable |
| Austin Booker | LB | CHI |  |  | name_found_position_incompatible |
| Jalyx Hunt | LB | PHI |  |  | name_found_position_incompatible |
| Dayo Odeyingbo | DL |  | 7649 |  | unique_name_position_team_unavailable |
| Jonah Elliss | LB | DEN |  |  | name_found_position_incompatible |
| Gabe Jacas | LB | NE |  |  | name_found_position_incompatible |
| Kendal Daniels | DB | ATL |  |  | name_found_position_incompatible |
| Elandon Roberts | LB |  | 3369 |  | unique_name_position_team_unavailable |
| Malik Harrison | LB |  | 6867 |  | unique_name_position_team_unavailable |
| Julian Okwara | DL |  | 6851 |  | unique_name_position_team_unavailable |
