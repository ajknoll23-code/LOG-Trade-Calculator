# FantasyPros ↔ Sleeper Unified Identity Report

Production resolver covering QB / RB / WR / TE / DL / LB / DB.

- FantasyPros tracked rows: **1033**
- Authoritative stable-ID matches: **928**
- Manual-review rows: **10**

## Coverage by position

| Pos | FP rows | Authoritative | Match rate | Candidate | Manual review |
|---|---:|---:|---:|---:|---:|
| QB | 79 | 71 | 89.9% | 73 | 2 |
| RB | 120 | 109 | 90.8% | 109 | 0 |
| WR | 177 | 161 | 91.0% | 161 | 0 |
| TE | 118 | 111 | 94.1% | 113 | 2 |
| DL | 178 | 160 | 89.9% | 160 | 0 |
| LB | 159 | 142 | 89.3% | 143 | 5 |
| DB | 202 | 174 | 86.1% | 174 | 1 |

## Match methods

- `name_collision_resolved_by_position_team`: **4**
- `name_found_position_incompatible`: **5**
- `name_position_team_confirmed`: **923**
- `no_sleeper_name_candidate`: **95**
- `previous_authoritative_stable_id_preserved`: **1**
- `unique_name_position_team_unavailable`: **5**

## Manual-review rows

These remain deliberately unresolved; downstream consumers must use existing fallback behavior rather than guess identity.

| Player | Pos | FP team | Candidate SID | Sleeper team | Method |
|---|---|---|---|---|---|
| Jake Browning | QB |  | 6111 |  | unique_name_position_team_unavailable |
| Desmond Ridder | QB |  | 8159 |  | unique_name_position_team_unavailable |
| Jack Stoll | TE |  | 7946 |  | unique_name_position_team_unavailable |
| Devin Culp | TE |  | 11820 | TB | unique_name_position_team_unavailable |
| Austin Booker | LB | CHI |  |  | name_found_position_incompatible |
| Jalyx Hunt | LB | PHI |  |  | name_found_position_incompatible |
| Jonah Elliss | LB | DEN |  |  | name_found_position_incompatible |
| Gabe Jacas | LB | NE |  |  | name_found_position_incompatible |
| Kendal Daniels | DB | ATL |  |  | name_found_position_incompatible |
| Elandon Roberts | LB |  | 3369 |  | unique_name_position_team_unavailable |
