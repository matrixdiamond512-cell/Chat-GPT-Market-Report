"""Regression tests for source-backed heading aliases and substantive SOP sections."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from reporting import report as report_model
import sync_latest_report_publication as publication


class VerifiedHeadingAliasTests(unittest.TestCase):
    def _canonical_report(self, slot: str) -> dict:
        path = ROOT / "reports" / f"2026-10-14_{slot}-00.json"
        return json.loads(path.read_text(encoding="utf-8"))

    def test_2026_10_14_original_headings_are_recognized_with_substantive_bodies(self):
        cases = (
            ("08", "金利・為替・クロスアセットの因果関係", "クロスアセット資金フロー"),
            ("12", "主要6市場の短期見通し（条件付き）", "個別市場見通し"),
        )
        for slot, original_heading, canonical in cases:
            with self.subTest(slot=slot):
                report = self._canonical_report(slot)
                sections = report_model.parse_sections(report["fullText"])
                found = [
                    section for section in sections
                    if section["heading"] == canonical
                    and original_heading in section["original_heading"]
                ]
                self.assertEqual(len(found), 1)
                body = "\n".join(found[0]["lines"]).strip()
                self.assertGreaterEqual(len("".join(body.split())), 24)
                publication.validate_sop_body(report)

    def test_incidental_body_mention_does_not_create_a_heading(self):
        prose = "本文では金利・為替・クロスアセットの因果関係と主要6市場の短期見通しに触れた。"
        self.assertIsNone(report_model.canonical_heading(prose))
        self.assertEqual(publication.sop_sections(prose), [])

    def test_heading_without_substantive_body_remains_blocked(self):
        with self.assertRaisesRegex(SystemExit, "empty or substantively insufficient"):
            publication.require_semantic_section(
                {},
                ["今日の相場テーマ"],
                r"今日の相場テーマ",
                "今日の相場テーマ",
                sections=[("今日の相場テーマ", "短い")],
            )


if __name__ == "__main__":
    unittest.main()
