# FantasyPros ↔ Sleeper Unified Identity Report

Production resolver covering QB / RB / WR / TE / DL / LB / DB.

- FantasyPros tracked rows: **1083**
- Authoritative stable-ID matches: **1067**
- Manual-review rows: **2**

## Coverage by position

| Pos | FP rows | Authoritative | Match rate | Candidate | Manual review |
|---|---:|---:|---:|---:|---:|
| QB | 80 | 78 | 97.5% | 78 | 0 |
| RB | 132 | 131 | 99.2% | 131 | 0 |
| WR | 203 | 201 | 99.0% | 201 | 0 |
| TE | 130 | 129 | 99.2% | 129 | 0 |
| DL | 177 | 174 | 98.3% | 174 | 1 |
| LB | 159 | 157 | 98.7% | 157 | 1 |
| DB | 202 | 197 | 97.5% | 197 | 0 |

## Match methods

- `name_collision_resolved_by_position_team`: **4**
- `name_found_position_incompatible`: **2**
- `name_position_team_confirmed`: **1037**
- `no_sleeper_name_candidate`: **14**
- `previous_authoritative_stable_id_preserved`: **23**
- `previous_authoritative_stable_id_preserved_position_changed`: **3**

## Manual-review rows

These remain deliberately unresolved; downstream consumers must use existing fallback behavior rather than guess identity.

| Player | Pos | FP team | Candidate SID | Sleeper team | Method |
|---|---|---|---|---|---|
| Rob Beal Jr. | DL | MIA |  |  | name_found_position_incompatible |
| Jonah Elliss | LB | DEN |  |  | name_found_position_incompatible |
