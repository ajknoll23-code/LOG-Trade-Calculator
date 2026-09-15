# Elite Surplus V1 — Development Preregistration

**Status: FROZEN DEVELOPMENT PLAN — research only. No production change is authorized.**

## Question

Does the current QB FV curve understate elite surplus strongly enough that a monotone post-FV QB spacing layer improves future relative-production calibration, without fitting to Josh Allen, Dak Prescott, KTC, package votes, or 2026 outcomes?

## Why this study exists

The prior read-only audit found that over the primary 4-week historical window QB1 produced about 2.612× the QB29 replacement denominator, QB5 2.089×, and QB12 1.613×. Historical QB1/QB12 production spacing was 1.635× while the current deployed FV QB1/QB12 spacing was 1.336×. Those already-seen numbers are **design evidence only**, not confirmation.

## Frozen candidate set

- **E0 — identity:** `g(x)=x`.
- **E1 — linear surplus stretch:** above replacement, `g(x)=1+c(x-1)`, `c∈[0.75,1.75]`.
- **E2 — power:** above replacement, `g(x)=x^gamma`, `gamma∈[0.75,2.0]`.
- **E3 — quadratic hinge:** above replacement, `g(x)=x+alpha(x-1)^2`, `alpha∈[0,0.5]`.

All candidates are identity at and below replacement, positive, continuous, monotone, QB-only, and forbidden from using player names.

## Historical development

- Fit candidate parameters on **2024 rolling folds only**.
- Primary target: future relative-production magnitude for the training-time top 12 QBs.
- Primary window: **4 weeks**; 2- and 6-week windows are robustness checks.
- Validate once on **2025 rolling folds**.
- A candidate needs at least **3% relative MAE improvement** over E0 on the 2025 top-12 primary metric and must pass all frozen safety gates.
- If none qualifies, stop. No rescue formula.

## Fresh confirmation

2026 Week 1 is already spent and cannot confirm this study. If one historical candidate qualifies, its class and parameter are frozen before prospective scoring. The intended fresh window is **2026 Weeks 2–8 inclusive**, evaluated once after Week 8 with no refit and no effect-based early stopping.

A prospective pass still cannot deploy anything automatically. The underlying Production V2, Age Curve V2, Replacement Level V2, and Position Weight V2 studies must be reviewed first.

