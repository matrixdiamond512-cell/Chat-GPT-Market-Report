#!/usr/bin/env python3
"""Run stock-session analysis with the Yahoo Japan TOPIX quote symbol.

The original stock-session module uses ^TOPX, which does not reliably return
Tokyo intraday data.  Yahoo Japan exposes TOPIX as 998405.T, so override only
that source while reusing the existing analysis implementation.
"""

from __future__ import annotations

import sys

import update_stock_sessions as stock_sessions


stock_sessions.TOKYO_SYMBOLS["topix"] = ("998405.T", "TOPIX")


if __name__ == "__main__":
    sys.exit(stock_sessions.main())
