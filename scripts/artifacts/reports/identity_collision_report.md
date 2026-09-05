# FantasyPros ↔ Sleeper Unified Identity Report

Production resolver covering QB / RB / WR / TE / DL / LB / DB.

- FantasyPros tracked rows: **1082**
- Authoritative stable-ID matches: **957**
- Manual-review rows: **27**

## Coverage by position

| Pos | FP rows | Authoritative | Match rate | Candidate | Manual review |
|---|---:|---:|---:|---:|---:|
| QB | 79 | 71 | 89.9% | 73 | 2 |
| RB | 132 | 118 | 89.4% | 121 | 3 |
| WR | 203 | 172 | 84.7% | 184 | 12 |
| TE | 129 | 119 | 92.2% | 124 | 5 |
| DL | 178 | 160 | 89.9% | 160 | 0 |
| LB | 159 | 143 | 89.9% | 144 | 4 |
| DB | 202 | 174 | 86.1% | 174 | 1 |

## Match methods

- `name_collision_resolved_by_position_team`: **4**
- `name_found_position_incompatible`: **4**
- `name_position_team_confirmed`: **950**
- `no_sleeper_name_candidate`: **98**
- `previous_authoritative_stable_id_preserved`: **2**
- `previous_authoritative_stable_id_preserved_position_changed`: **1**
- `unique_name_position_team_unavailable`: **23**

## Manual-review rows

These remain deliberately unresolved; downstream consumers must use existing fallback behavior rather than guess identity.

| Player | Pos | FP team | Candidate SID | Sleeper team | Method |
|---|---|---|---|---|---|
| Jake Browning | QB |  | 6111 |  | unique_name_position_team_unavailable |
| Desmond Ridder | QB |  | 8159 |  | unique_name_position_team_unavailable |
| Jarquez Hunter | RB |  | 11569 |  | unique_name_position_team_unavailable |
| Terrell Jennings | RB |  | 12412 |  | unique_name_position_team_unavailable |
| Eric Gray | RB |  | 10223 |  | unique_name_position_team_unavailable |
| Brandin Cooks | WR |  | 2197 |  | unique_name_position_team_unavailable |
| Nick Westbrook-Ikhine | WR |  | 7496 | IND | unique_name_position_team_unavailable |
| JuJu Smith-Schuster | WR |  | 4040 |  | unique_name_position_team_unavailable |
| Tahj Washington | WR |  | 11821 |  | unique_name_position_team_unavailable |
| Malik Heath | WR |  | 11210 | ATL | unique_name_position_team_unavailable |
| Xavier Weaver | WR |  | 11921 |  | unique_name_position_team_unavailable |
| Cody White | WR |  | 7039 | LV | unique_name_position_team_unavailable |
| Anthony Gould | WR |  | 11762 | IND | unique_name_position_team_unavailable |
| Ja'Corey Brooks | WR |  | 12532 |  | unique_name_position_team_unavailable |
| Xavier Gipson | WR |  | 11306 |  | unique_name_position_team_unavailable |
| Malik Turner | WR |  | 5781 |  | unique_name_position_team_unavailable |
| Tejhaun Palmer | WR |  | 11802 |  | unique_name_position_team_unavailable |
| Tanner Conner | TE |  | 8849 |  | unique_name_position_team_unavailable |
| Anthony Firkser | TE |  | 4435 |  | unique_name_position_team_unavailable |
| John FitzPatrick | TE |  | 8500 |  | unique_name_position_team_unavailable |
| Jack Stoll | TE |  | 7946 |  | unique_name_position_team_unavailable |
| Devin Culp | TE |  | 11820 | TB | unique_name_position_team_unavailable |
| Austin Booker | LB | CHI |  |  | name_found_position_incompatible |
| Jonah Elliss | LB | DEN |  |  | name_found_position_incompatible |
| Gabe Jacas | LB | NE |  |  | name_found_position_incompatible |
| Kendal Daniels | DB | ATL |  |  | name_found_position_incompatible |
| Elandon Roberts | LB |  | 3369 |  | unique_name_position_team_unavailable |
