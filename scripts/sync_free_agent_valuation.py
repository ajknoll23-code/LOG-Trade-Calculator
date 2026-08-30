#!/usr/bin/env python3
"""Compatibility wrapper for scripts/sync/sync_free_agent_valuation.py.

New code should import or execute the sync implementation directly.
This wrapper temporarily preserves existing workflow and Python import paths,
including the private helper functions used by validation code.
"""

from sync import sync_free_agent_valuation as _impl


# Re-export every non-dunder attribute, including private helpers such as
# _extract_core(), _extract_const_object(), and _extract_function().
for _name in dir(_impl):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_impl, _name)


if __name__ == "__main__":
    raise SystemExit(_impl.main())
