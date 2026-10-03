# Player Role V2 — B41F Final Development Model Freeze

- Training data: **exact B41D 2019–2024 modeling artifact**
- Modeling rows: **85,648**
- Selected family at every position: **nonnegative ridge linear**
- B41E tier thresholds changed: **No**
- 2025 holdout opened: **No**
- 2026 Week 4 opened: **No**
- Production model weights fitted: **Yes**
- Production deployed: **No**
- Production change authorized: **No**

## Final alpha selected on six-season development LOSO

| Position | Alpha | Features |
|---|---:|---:|
| QB | 0 | 14 |
| RB | 0.1 | 17 |
| WR | 1 | 20 |
| TE | 0 | 20 |
| K | 10 | 14 |
| DL | 0.01 | 23 |
| LB | 0.1 | 23 |
| DB | 0 | 20 |

Stored in-sample fit statistics are descriptive only, not validation.
B41C3 must pass before the 2025 holdout is opened.
If B41C3 passes, the frozen score + B41E tier system may be evaluated once on untouched 2025 with no retuning.
