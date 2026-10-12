from __future__ import annotations

import hashlib
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from reporting.infographic_source import ReportBodySourceError, REQUIRED_0800_HEADINGS, resolve_report_body


def complete_0800_body() -> str:
    headings = "\n\n".join(f"{i}. {heading}\n確認済みのテスト本文。" for i, heading in enumerate(REQUIRED_0800_HEADINGS, start=1))
    return f"マーケットレポート｜2026/10/09（金）08:00\n\n{headings}\n\nクロスチェック結果\nテスト記録。\n"


class InfographicSourceResolutionTests(unittest.TestCase):
    def test_chat_transcript_has_priority_and_body_is_hashed_verbatim(self):
        chat = complete_0800_body()
        docs = complete_0800_body().replace("テスト記録。", "別のDrive本文。")
        selected = resolve_report_body("2026-10-09_08-00", chat_transcript=chat, google_docs=docs)
        self.assertEqual("CHAT_TRANSCRIPT", selected["source"])
        self.assertEqual(chat, selected["body"])
        self.assertEqual(hashlib.sha256(chat.encode("utf-8")).hexdigest(), selected["body_hash"])

    def test_incomplete_chat_falls_through_to_complete_docs(self):
        docs = complete_0800_body()
        selected = resolve_report_body("2026-10-09_08-00", chat_transcript="title only", google_docs=docs)
        self.assertEqual("GOOGLE_DOCS", selected["source"])
        self.assertEqual("REJECTED", selected["attempts"][0]["status"])

    def test_saved_google_docs_body_is_accepted_without_chat_transcript(self):
        docs = complete_0800_body()
        selected = resolve_report_body("2026-10-09_08-00", google_docs=docs)
        self.assertEqual("GOOGLE_DOCS", selected["source"])
        self.assertEqual(docs, selected["body"])
        self.assertEqual(hashlib.sha256(docs.encode("utf-8")).hexdigest(), selected["body_hash"])

    def test_incomplete_chat_and_docs_fall_through_to_canonical_json(self):
        body = complete_0800_body()
        canonical = json.dumps({"report_id": "2026-10-09_08-00", "full_text": body}, ensure_ascii=False)
        selected = resolve_report_body("2026-10-09_08-00", chat_transcript="", google_docs="partial", canonical_json=canonical)
        self.assertEqual("CANONICAL_JSON", selected["source"])

    def test_wrong_title_and_missing_crosscheck_are_rejected(self):
        body = complete_0800_body().replace("2026/10/09（金）08:00", "2026/10/08（木）08:00", 1)
        with self.assertRaisesRegex(ReportBodySourceError, "REPORT_BODY_NOT_FOUND"):
            resolve_report_body("2026-10-09_08-00", chat_transcript=body)
        no_crosscheck = complete_0800_body().replace("クロスチェック結果", "未完了")
        with self.assertRaisesRegex(ReportBodySourceError, "REPORT_BODY_NOT_FOUND"):
            resolve_report_body("2026-10-09_08-00", chat_transcript=no_crosscheck)

    def test_market_snapshot_is_not_an_accepted_fallback(self):
        with self.assertRaises(TypeError):
            resolve_report_body("2026-10-09_08-00", market_snapshot={"body": complete_0800_body()})


if __name__ == "__main__":
    unittest.main()
