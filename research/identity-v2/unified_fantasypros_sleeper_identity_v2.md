# Unified FantasyPros ↔ Sleeper Identity V2 Audit

## Decision

**STRUCTURALLY_CLEAN_REVIEW_COVERAGE_BEFORE_PROMOTION**

**RESEARCH ONLY. `scripts/identity_crosswalk.json` was not changed by this audit.**

## Structural summary

- FantasyPros tracked rows: **1034**
- Sleeper stable IDs in current projection universe: **9419**
- Authoritative matches: **922**
- Manual-review rows: **17**
- Duplicate authoritative Sleeper assignment groups: **0**
- Existing IDP V1 authoritative conflicts: **0**

## Coverage by position

| Pos | FantasyPros rows | Authoritative | Match rate | Candidate identified | Manual review |
|---|---:|---:|---:|---:|---:|
| QB | 79 | 70 | 88.6% | 73 | 3 |
| RB | 119 | 107 | 89.9% | 107 | 1 |
| WR | 179 | 161 | 89.9% | 162 | 1 |
| TE | 118 | 110 | 93.2% | 113 | 3 |
| DL | 177 | 158 | 89.3% | 160 | 2 |
| LB | 159 | 141 | 88.7% | 143 | 6 |
| DB | 203 | 175 | 86.2% | 175 | 1 |

## Match methods

- `name_collision_resolved_by_position_team`: **4**
- `name_found_position_incompatible`: **6**
- `name_position_team_confirmed`: **918**
- `no_sleeper_name_candidate`: **95**
- `unique_name_position_team_mismatch`: **1**
- `unique_name_position_team_unavailable`: **10**

## Existing IDP V1 comparison

- `v1_authoritative_preserved`: **474**

## Manual-review rows

These are deliberately unresolved. The audit never silently guesses them.

| Player | Pos | FP team | Candidate SID | Sleeper team | Method | Name cand. | Pos cand. |
|---|---|---|---|---|---|---:|---:|
| Brady Cook | QB | FA | 12538 |  | unique_name_position_team_unavailable | 1 | 1 |
| Jake Browning | QB | FA | 6111 |  | unique_name_position_team_unavailable | 1 | 1 |
| Desmond Ridder | QB | FA | 8159 |  | unique_name_position_team_unavailable | 1 | 1 |
| Max Bredeson | RB | MIN |  |  | name_found_position_incompatible | 1 | 0 |
| Xavier Weaver | WR | FA | 11921 |  | unique_name_position_team_unavailable | 1 | 1 |
| Justin Joly | TE | FA | 13400 |  | unique_name_position_team_unavailable | 1 | 1 |
| Jack Stoll | TE | FA | 7946 |  | unique_name_position_team_unavailable | 1 | 1 |
| Devin Culp | TE | FA | 11820 | TB | unique_name_position_team_mismatch | 1 | 1 |
| Austin Booker | LB | CHI |  |  | name_found_position_incompatible | 1 | 0 |
| Jalyx Hunt | LB | PHI |  |  | name_found_position_incompatible | 1 | 0 |
| Dayo Odeyingbo | DL | FA | 7649 |  | unique_name_position_team_unavailable | 1 | 1 |
| Jonah Elliss | LB | DEN |  |  | name_found_position_incompatible | 1 | 0 |
| Gabe Jacas | LB | NE |  |  | name_found_position_incompatible | 1 | 0 |
| Kendal Daniels | DB | ATL |  |  | name_found_position_incompatible | 1 | 0 |
| Elandon Roberts | LB | FA | 3369 |  | unique_name_position_team_unavailable | 1 | 1 |
| Malik Harrison | LB | FA | 6867 |  | unique_name_position_team_unavailable | 1 | 1 |
| Julian Okwara | DL | FA | 6851 |  | unique_name_position_team_unavailable | 1 | 1 |

## Promotion rule

This audit does **not** promote anything automatically. After reviewing coverage and every unresolved/conflicting row,
the validated matching logic can be moved into the production resolver and only then replace the IDP-only crosswalk.
