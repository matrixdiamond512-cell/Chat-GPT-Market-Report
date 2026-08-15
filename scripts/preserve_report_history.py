from __future__ import annotations

# Backward-compatible entry point.
# The canonical implementation lives in build_reports.py so all report-history
# rebuilds use the same non-destructive validation and legacy backfill rules.
from build_reports import main


if __name__ == "__main__":
    main()
