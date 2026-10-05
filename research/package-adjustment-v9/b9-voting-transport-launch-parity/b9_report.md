# Package Adjustment V9 — B9 Frozen Voting Transport Launch Parity

- Decision: `PASS_B9_LAUNCH_PARITY_DEPLOY_TRANSPORT_URL_DISTRIBUTION_CONDITIONAL_ON_P1_TO_P6`
- B8 catalog binding: `dd6391691c91e0ee8172fb3a89b0b53417432e8aaf991f2ab048048a715cac62`
- Frozen voter slots: **40**
- Ballots per slot: **24**
- Synthetic transport roundtrips: **1920 / 1920 PASS**
- Browser hidden-evaluator access: **FALSE**
- Reverse patch recovers pre-B9 index exactly: **TRUE**
- Normal KTC V9-row isolation: **PASS** (`__pkgv9val__|` excluded before daily cap / Bradley-Terry)
- KTC scoring logic changed: **FALSE**
- Production V9 activation authorized: **FALSE**
- Human outcome analysis authorized: **FALSE**
- URL distribution: **CONDITIONAL ON P1-P6**

B9 deploys the B8-authorized session-aware V9 voting transport and the narrow `__pkgv9val__|` reserved-row exclusion required by B8. URL distribution is authorized only after launch preconditions P1-P6 are satisfied and recorded in a launch-checklist file committed on `main`.
