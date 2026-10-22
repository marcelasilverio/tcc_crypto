"""Compatibility command for the explicit daily prepare stage.

Run prepare first before model commands. Use --overwrite to replace derived outputs.
"""

from __future__ import annotations

import sys

from tcc_crypto.daily import main

if __name__ == "__main__":
    main(["prepare", "--profile", "pilot", *sys.argv[1:]])
