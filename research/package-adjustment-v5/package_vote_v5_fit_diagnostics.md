# Package Adjustment V5 — Composition Fit Diagnostics

**RESEARCH ONLY — no automatic production change is allowed.**

- Generated: `2026-09-10T15:00:24.476413+00:00`
- Status: `research_diagnostics_complete`
- Production revision remains: `v1.5-audit-step6-scope-ui-idp`
- Counted V5 votes: `600`
- Unique V5 voters: `30`
- Diagnostic data gates passed: `True`

## Estimated 50% indifference by composition

| Composition | Indifference ratio | 90% voter-cluster bootstrap CI | Bootstrap bracketed |
|---:|---:|---:|---:|
| 50/50 | 1.594x | 1.556–1.750x | 75.4% |
| 55/45 | 1.656x | 1.480–1.718x | 97.4% |
| 60/40 | 1.531x | 1.395–1.563x | 97.2% |
| 65/35 | unbracketed | 1.358–1.400x | 39.8% |
| 70/30 | unbracketed | 1.342–1.400x | 32.2% |
| 75/25 | unbracketed | 1.265–1.300x | 24.2% |

## Interpretation guardrails

- Primary estimator: voter-capped weighted isotonic package-choice curve within each composition band.
- 50% indifference is interpolated only between tested ratio cells.
- No extrapolation is allowed outside a composition band's tested ratio range.
- Uncertainty uses a voter-cluster bootstrap so one heavy voter is not treated as many independent people.
- Any future production change still requires a separate reviewed hardening step.

## Production isolation

- Fundamental Value unchanged.
- Market Value unchanged.
- Draft-pick values unchanged.
- Team Utility unchanged.
- Controlled-live Package Adjustment V1.5 formula unchanged.
- `production_promotion_allowed` remains `False` in this diagnostic artifact.
