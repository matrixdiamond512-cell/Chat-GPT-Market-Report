"""Truthful stage summaries for importing saved market-report sources.

Importing a Google Doc into append-only canonical history does not prove that
its evidence, publication receipt, Pages deployment, or public readback passed.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def format_ingestion_status_lines(
    to_write: Mapping[tuple[str, str], tuple[dict[str, Any], dict[str, Any] | None]],
    to_promote: Mapping[tuple[str, str], tuple[dict[str, Any], dict[str, Any]]],
) -> list[str]:
    """Describe completed importer stages without claiming Pages publication."""
    lines: list[str] = []
    written = sorted(to_write)
    archive_only = sorted(key for key, (_, receipt) in to_write.items() if receipt is None)
    readback_verified = sorted(
        key for key, (report, receipt) in to_write.items()
        if receipt is not None and report.get("report_status") == "DOC_READBACK_PASS"
    )
    unknown = sorted(
        key for key, (report, receipt) in to_write.items()
        if receipt is not None and report.get("report_status") != "DOC_READBACK_PASS"
    )
    promoted = sorted(to_promote)

    if written:
        lines.append("CANONICAL_SOURCE_INGESTION_COMPLETE: " + ", ".join(_slot(key) for key in written))
    if archive_only:
        lines.append(
            "SOURCE_ARCHIVED_ONLY (formal publication not established): "
            + ", ".join(_slot(key) for key in archive_only)
        )
    if readback_verified:
        lines.append(
            "DOC_READBACK_RECEIPT_RECORDED (Pages deployment/public readback not verified): "
            + ", ".join(_slot(key) for key in readback_verified)
        )
    if unknown:
        lines.append(
            "CANONICAL_INGESTION_STATUS_UNKNOWN (receipt/status pairing requires review): "
            + ", ".join(_slot(key) for key in unknown)
        )
    if promoted:
        lines.append(
            "ARCHIVED_SOURCE_PROMOTED_TO_CANONICAL (Pages deployment/public readback not verified): "
            + ", ".join(_slot(key) for key in promoted)
        )
    return lines


def _slot(key: tuple[str, str]) -> str:
    return f"{key[0]} {key[1]}"