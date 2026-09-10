#!/usr/bin/env python3
"""Revision-aware exact-live Package Adjustment OOS dispatcher.

This file intentionally contains no Package Adjustment formula.
It selects the versioned exact-live implementation based only on the
controlled-live production revision recorded in live_deployment.json.
Unknown revisions fail closed.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LIVE = ROOT / "research/package-adjustment-production-candidate-v1/live_deployment.json"
VALIDATION_DIR = ROOT / "scripts/validation"

REVISION_TO_SCRIPT = {
    "v1.5-audit-step6-scope-ui-idp": VALIDATION_DIR / "package_adjustment_exact_live_oos_v1_5.py",
    "v1.6-v5-size2-composition-overlay": VALIDATION_DIR / "package_adjustment_exact_live_oos_v1_6.py",
}

def resolve_revision():
    if not LIVE.exists():
        raise RuntimeError(f"Missing live deployment metadata: {LIVE}")
    live = json.loads(LIVE.read_text(encoding="utf-8"))
    if live.get("status") != "controlled_live":
        raise RuntimeError(
            f"Package Adjustment is not controlled_live: {live.get('status')}"
        )
    if live.get("production_formula_enabled") is not True:
        raise RuntimeError("Package Adjustment production formula is not enabled")

    revision = str(live.get("production_revision") or "")
    script = REVISION_TO_SCRIPT.get(revision)
    if script is None:
        raise RuntimeError(
            f"Unsupported Package Adjustment production revision: {revision!r}"
        )
    return revision, script

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--resolve-only",
        action="store_true",
        help="Validate revision routing without executing the selected monitor.",
    )
    args = parser.parse_args()

    revision, script = resolve_revision()

    if args.resolve_only:
        if revision == "v1.5-audit-step6-scope-ui-idp" and not script.exists():
            raise RuntimeError(f"Current V1.5 monitor implementation missing: {script}")
        print(f"PACKAGE_ADJUSTMENT_OOS_DISPATCH_REVISION={revision}")
        print(f"PACKAGE_ADJUSTMENT_OOS_DISPATCH_SCRIPT={script.relative_to(ROOT)}")
        print("PACKAGE_ADJUSTMENT_OOS_DISPATCH_RESOLVE=PASS")
        return

    if not script.exists():
        raise RuntimeError(
            f"Exact-live OOS implementation missing for {revision}: {script}"
        )

    print(f"Dispatching Package Adjustment OOS monitor for {revision}")
    subprocess.run(
        [sys.executable, str(script)],
        cwd=ROOT,
        check=True,
    )

if __name__ == "__main__":
    main()
