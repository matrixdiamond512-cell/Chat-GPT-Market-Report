#!/usr/bin/env python3
"""Safely sync ONLY the USDJPY volume JSON publisher in the existing Apps Script project.

The shared deploy script retains its exact SHA preflight and post-write readback.
Never deploy any market-report or unrelated files from this entrypoint.
"""
import deploy_market_report_apps_script as sync

sync.TARGET_FILES = ("UsdJpyVolumeJsonFlexibleSync",)

if __name__ == "__main__":
    sync.main()
