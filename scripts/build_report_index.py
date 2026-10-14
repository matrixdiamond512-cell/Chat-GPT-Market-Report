#!/usr/bin/env python3
"""Compatibility entry point for the canonical report-history builder.

All history validation and persistence rules live in ``build_reports.py``.
Keeping this command preserves existing workflow/operator entry points without
maintaining a second set of index rules.
"""
from build_reports import main


if __name__ == "__main__":
    main()
