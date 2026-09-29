# FantasyPros ↔ Sleeper Unified Identity Report

Production resolver covering QB / RB / WR / TE / DL / LB / DB.

- FantasyPros tracked rows: **1083**
- Authoritative stable-ID matches: **983**
- Manual-review rows: **2**

## Coverage by position

| Pos | FP rows | Authoritative | Match rate | Candidate | Manual review |
|---|---:|---:|---:|---:|---:|
| QB | 80 | 74 | 92.5% | 74 | 0 |
| RB | 132 | 121 | 91.7% | 121 | 0 |
| WR | 203 | 184 | 90.6% | 184 | 0 |
| TE | 130 | 124 | 95.4% | 125 | 1 |
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
- `phase16_batch_stable_id_corroboration`: **3**
- `phase18_batch_stable_id_corroboration`: **3**
- `previous_authoritative_stable_id_preserved`: **7**
- `previous_authoritative_stable_id_preserved_position_changed`: **3**
- `unique_name_position_team_unavailable`: **1**

## Manual-review rows

These remain deliberately unresolved; downstream consumers must use existing fallback behavior rather than guess identity.

| Player | Pos | FP team | Candidate SID | Sleeper team | Method |
|---|---|---|---|---|---|
| Devin Culp | TE |  | 11820 | TB | unique_name_position_team_unavailable |
| Jonah Elliss | LB | DEN |  |  | name_found_position_incompatible |
