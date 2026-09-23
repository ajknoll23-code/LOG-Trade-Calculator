# FantasyPros ↔ Sleeper Unified Identity Report

Production resolver covering QB / RB / WR / TE / DL / LB / DB.

- FantasyPros tracked rows: **1083**
- Authoritative stable-ID matches: **970**
- Manual-review rows: **15**

## Coverage by position

| Pos | FP rows | Authoritative | Match rate | Candidate | Manual review |
|---|---:|---:|---:|---:|---:|
| QB | 80 | 72 | 90.0% | 74 | 2 |
| RB | 132 | 120 | 90.9% | 121 | 1 |
| WR | 203 | 177 | 87.2% | 184 | 7 |
| TE | 130 | 122 | 93.8% | 125 | 3 |
| DL | 177 | 159 | 89.8% | 159 | 0 |
| LB | 159 | 145 | 91.2% | 146 | 2 |
| DB | 202 | 175 | 86.6% | 175 | 0 |

## Match methods

- `name_collision_resolved_by_position_team`: **4**
- `name_found_position_incompatible`: **1**
- `name_position_team_confirmed`: **956**
- `no_sleeper_name_candidate`: **98**
- `previous_authoritative_stable_id_preserved`: **7**
- `previous_authoritative_stable_id_preserved_position_changed`: **3**
- `unique_name_position_team_unavailable`: **14**

## Manual-review rows

These remain deliberately unresolved; downstream consumers must use existing fallback behavior rather than guess identity.

| Player | Pos | FP team | Candidate SID | Sleeper team | Method |
|---|---|---|---|---|---|
| Jake Browning | QB |  | 6111 |  | unique_name_position_team_unavailable |
| Desmond Ridder | QB |  | 8159 |  | unique_name_position_team_unavailable |
| Terrell Jennings | RB |  | 12412 |  | unique_name_position_team_unavailable |
| JuJu Smith-Schuster | WR |  | 4040 |  | unique_name_position_team_unavailable |
| Tahj Washington | WR |  | 11821 |  | unique_name_position_team_unavailable |
| Malik Heath | WR |  | 11210 | ATL | unique_name_position_team_unavailable |
| Xavier Weaver | WR |  | 11921 |  | unique_name_position_team_unavailable |
| Ja'Corey Brooks | WR |  | 12532 |  | unique_name_position_team_unavailable |
| Malik Turner | WR |  | 5781 |  | unique_name_position_team_unavailable |
| Tejhaun Palmer | WR |  | 11802 |  | unique_name_position_team_unavailable |
| Anthony Firkser | TE |  | 4435 |  | unique_name_position_team_unavailable |
| John FitzPatrick | TE |  | 8500 |  | unique_name_position_team_unavailable |
| Devin Culp | TE |  | 11820 | TB | unique_name_position_team_unavailable |
| Jonah Elliss | LB | DEN |  |  | name_found_position_incompatible |
| Elandon Roberts | LB |  | 3369 |  | unique_name_position_team_unavailable |
