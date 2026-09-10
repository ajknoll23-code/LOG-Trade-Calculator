# Package Adjustment — OOS Transition Dispatcher

**No production change and no permanent workflow change in this setup.**

The exact-live OOS monitor is now revision-routed by a small normal Python dispatcher. Current V1.5 routes to the externalized V1.5 implementation. Future V1.6 will route to a separate versioned implementation and fails closed until that file exists.

The V1.5 implementation still accepts its original frozen workflow SHA. It additionally accepts only a workflow containing the reviewed marker `PACKAGE_ADJUSTMENT_OOS_DISPATCHER_V1`, allowing the giant inline workflow to be replaced manually by a thin dispatcher runner without silently accepting arbitrary workflow drift.

Next: manually replace the permanent exact-live workflow with the thin dispatcher workflow and prove it still runs cleanly on current V1.5.
