# Package Adjustment Audit Step 2 — Production Hardening

Generated: 2026-09-09T00:12:58.945596+00:00

## Decision

The 3-player Package Adjustment now **fails closed outside the frozen V4 empirical
composition envelope**. The old 16% smallest-piece shortcut has been removed.

V4 did not experimentally vary arbitrary package composition. It held intended
composition near 45/33/22 and varied package/target ratio. Therefore production
support is restricted to the composition region actually represented by the 100
frozen V4 challenges.

## Live 3-player composition envelope

- Largest meaningful package share: **41.991% – 46.962%**
- Middle meaningful package share: **30.827% – 36.725%**
- Smallest meaningful package share: **21.202% – 22.473%**

The three meaningful pieces are sorted by FV and normalized over meaningful
package FV. A 3-meaningful-player trade outside any one of these bounds receives
no Package Adjustment premium.

## Preserved invariants

- **100 / 100** frozen V4 challenges pass the new envelope.
- Nominal **45/33/22** composition passes.
- Sub-6%-of-target throw-ins preserve the same 3-player classification because
  they are excluded from the composition denominator while retaining full raw FV.
- A fourth meaningful player remains unsupported.
- 2-player calibration is unchanged.
- Fundamental Value, Market Value, draft-pick value, and Team Utility are unchanged.

## Adversarial checks

Every deliberately out-of-envelope test shape was rejected, including 55/24/21
and just-outside boundary probes.

## Audit state

Step 2 is complete. The next gate is **Step 3 — Evidence-bounded 2-player
composition policy**.
