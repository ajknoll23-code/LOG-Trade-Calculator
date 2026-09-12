# Package Adjustment NextGen V2 — Prospective Restart Amendment: 30/Day

**Status: FROZEN RESTART AMENDMENT — production V1.6 unchanged.**

The initial prospective activation retained a 20-vote daily cap even though
the intended prospective rule was **30 votes/day and 30 effective votes
lifetime per voter**.

To preserve a clean prospective study:

- **All existing prospective rows before the replacement cutoff are invalidated.**
- Their choices were **not inspected**.
- Raw rows remain in the transport only as an audit trail; they do not count.
- Replacement valid-ballot start: `2026-09-12T12:59:45.410967+00:00`
- Daily valid vote cap per voter: **30**
- Effective lifetime cap per voter: **30**
- Minimum distinct voters: **30**
- First checkpoint: **900 effective votes**
- Backup/hard cap: **1000 effective votes**
- Every one of the 24 cells still requires **≥15 effective votes and ≥10 voters**.
- Catalog, M2b parameters, equal-cell sampler, transport namespace, and
  production V1.6 are unchanged.
