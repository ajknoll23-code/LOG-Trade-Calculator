#!/usr/bin/env python3
"""Compatibility wrapper for scripts/sync/sync_sleeper.py.

New code should import or execute the sync implementation directly.
This wrapper temporarily preserves existing workflow and Python import paths
while the repository reorganization is completed.
"""

from sync.sync_sleeper import *  # noqa: F401,F403


if __name__ == "__main__":
    main()
