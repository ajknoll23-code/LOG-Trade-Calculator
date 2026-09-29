# FantasyPros ↔ Sleeper Unified Identity Report

Production resolver covering QB / RB / WR / TE / DL / LB / DB.

- FantasyPros tracked rows: **1083**
- Authoritative stable-ID matches: **977**
- Manual-review rows: **8**

## Coverage by position

| Pos | FP rows | Authoritative | Match rate | Candidate | Manual review |
|---|---:|---:|---:|---:|---:|
| QB | 80 | 74 | 92.5% | 74 | 0 |
| RB | 132 | 121 | 91.7% | 121 | 0 |
| WR | 203 | 180 | 88.7% | 184 | 4 |
| TE | 130 | 122 | 93.8% | 125 | 3 |
| DL | 177 | 159 | 89.8% | 159 | 0 |
| LB | 159 | 146 | 91.8% | 146 | 1 |
| DB | 202 | 175 | 86.6% | 175 | 0 |

## Match methods

- `name_collision_resolved_by_position_team`: **4**
- `name_found_position_incompatible`: **1**
- `name_position_team_confirmed`: **956**
- `no_sleeper_name_candidate`: **98**
- `phase10_independent_stable_id_corroboration`: **1**
- `phase12_batch_stable_id_corroboration`: **3**
- `phase14_batch_stable_id_corroboration`: **3**
- `previous_authoritative_stable_id_preserved`: **7**
- `previous_authoritative_stable_id_preserved_position_changed`: **3**
- `unique_name_position_team_unavailable`: **7**

## Manual-review rows

These remain deliberately unresolved; downstream consumers must use existing fallback behavior rather than guess identity.

| Player | Pos | FP team | Candidate SID | Sleeper team | Method |
|---|---|---|---|---|---|
| Xavier Weaver | WR |  | 11921 |  | unique_name_position_team_unavailable |
| Ja'Corey Brooks | WR |  | 12532 |  | unique_name_position_team_unavailable |
| Malik Turner | WR |  | 5781 |  | unique_name_position_team_unavailable |
| Tejhaun Palmer | WR |  | 11802 |  | unique_name_position_team_unavailable |
| Anthony Firkser | TE |  | 4435 |  | unique_name_position_team_unavailable |
| John FitzPatrick | TE |  | 8500 |  | unique_name_position_team_unavailable |
| Devin Culp | TE |  | 11820 | TB | unique_name_position_team_unavailable |
| Jonah Elliss | LB | DEN |  |  | name_found_position_incompatible |
