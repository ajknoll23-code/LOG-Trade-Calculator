#!/usr/bin/env python3
"""Compatibility wrapper for scripts/model/idp_v1_projection.py.

New code should import or execute the model implementation directly.
This wrapper temporarily preserves existing root import and execution paths
while the repository reorganization is completed.
"""

from model import idp_v1_projection as _impl


for _name in dir(_impl):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_impl, _name)


if __name__ == "__main__":
    raise SystemExit(_impl.run_selftest())
