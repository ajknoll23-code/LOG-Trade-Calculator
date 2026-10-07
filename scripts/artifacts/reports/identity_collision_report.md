# FantasyPros ↔ Sleeper Unified Identity Report

Production resolver covering QB / RB / WR / TE / DL / LB / DB.

- FantasyPros tracked rows: **1083**
- Authoritative stable-ID matches: **984**
- Manual-review rows: **1**

## Coverage by position

| Pos | FP rows | Authoritative | Match rate | Candidate | Manual review |
|---|---:|---:|---:|---:|---:|
| QB | 80 | 74 | 92.5% | 74 | 0 |
| RB | 132 | 121 | 91.7% | 121 | 0 |
| WR | 203 | 184 | 90.6% | 184 | 0 |
| TE | 130 | 125 | 96.2% | 125 | 0 |
| DL | 177 | 159 | 89.8% | 159 | 0 |
| LB | 159 | 146 | 91.8% | 146 | 1 |
| DB | 202 | 175 | 86.6% | 175 | 0 |

## Match methods

- `name_collision_resolved_by_position_team`: **4**
- `name_found_position_incompatible`: **1**
- `name_position_team_confirmed`: **955**
- `no_sleeper_name_candidate`: **98**
- `previous_authoritative_stable_id_preserved`: **22**
- `previous_authoritative_stable_id_preserved_position_changed`: **3**

## Manual-review rows

These remain deliberately unresolved; downstream consumers must use existing fallback behavior rather than guess identity.

| Player | Pos | FP team | Candidate SID | Sleeper team | Method |
|---|---|---|---|---|---|
| Jonah Elliss | LB | DEN |  |  | name_found_position_incompatible |
