# Draft Pick FV V7 — Phase 2 Residual Router Recovery

**Decision:** `FREEZE_V7_PHASE2_RESIDUAL_ROUTER_RECOVERY_AUTHORIZED`

Transport-only recovery for the exact 22 residual R25 batches after the completed 52-batch targeted pass.

- Frozen candidate/source membership is unchanged.
- No new league search or source substitution is allowed.
- Only the same frozen MFL year/league/API request may be retried through MFL-owned routing.
- No arbitrary numeric shard guessing is allowed.
- TLS verification remains the default; insecure TLS fallback is restricted to a shard hostname returned by a verified MFL HTTPS redirect.
- Transport failure remains fatal and cannot become an ineligibility decision.
- No player outcomes, 2024 holdout outcomes, market/vote data, fitting, scoring, or production changes.

Residual batches:
- 2018: 0, 3, 5, 13, 24, 31, 33, 35, 36, 39, 41
- 2019: 0, 15, 24, 25, 29, 37
- 2020: 12, 34, 39
- 2021: 28, 34
- 2022: none
- 2023: none

Observed failure taxonomy:
- connect_timeout: 8
- dns_resolution_failure: 6
- expired_tls_certificate: 1
- redirect_loop: 4
- redirect_loop_plus_timeout: 2
- repeated_non_json_response: 1

