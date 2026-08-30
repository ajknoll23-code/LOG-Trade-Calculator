#!/usr/bin/env python3
"""Compatibility wrapper for scripts/utilities/generate_player_positions.py.

New code should import or execute the utilities implementation directly.
This wrapper temporarily preserves existing workflow and Python import paths
while the repository reorganization is completed.
"""

from utilities.generate_player_positions import *  # noqa: F401,F403


if __name__ == "__main__":
    main()
