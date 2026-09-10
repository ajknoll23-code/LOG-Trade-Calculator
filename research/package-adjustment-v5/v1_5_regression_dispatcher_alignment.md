# Package Adjustment V1.5 — Repo Regression Dispatcher Alignment

**Production formula unchanged.**

The permanent Package Adjustment repo validator now accepts either the original frozen V1.5 OOS workflow SHA or the specifically reviewed thin dispatcher workflow marker. Arbitrary workflow drift still fails closed.

- Current production remains `v1.5-audit-step6-scope-ui-idp`.
- V1.5 Package Adjustment permanent regression: **PASS**.
- Full repository regression suite: **PASS**.
- Thin permanent OOS workflow: unchanged by this alignment.
- V1.5 is now a healthy rollback target before any V1.6 promotion.
