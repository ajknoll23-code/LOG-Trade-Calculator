#!/usr/bin/env python3
"""Compatibility wrapper for scripts/model/ppg_pipeline.py.

New code should import or execute the model implementation directly.
This wrapper temporarily preserves the old root execution path while the
repository reorganization is completed.
"""

from model.ppg_pipeline import *  # noqa: F401,F403


if __name__ == "__main__":
    raise SystemExit(main())
