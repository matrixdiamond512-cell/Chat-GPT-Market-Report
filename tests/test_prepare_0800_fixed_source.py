from __future__ import annotations

import hashlib
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from prepare_0800_fixed_source import prepare_candidate


class Prepare0800FixedSourceTests(unittest.TestCase):
    def test_snapshot_is_reproducible_and_extractive_panels_bind_existing_text(self):
        title = "マーケットレポート｜2026/10/09（金）08:00"
        leadership = "①原油 ②米長期金利 ③AI・半導体株。"
        news = "AI投資収益性への懸念、中東情勢と原油高。"
        conclusion = "原油高が続き、慎重姿勢が優勢。"
        body = "\n\n".join((title, "今日の主導市場\n" + leadership,
                             "重要ニュース・イベント\n" + news, "結論\n" + conclusion))
        body_hash = hashlib.sha256(body.encode("utf-8")).hexdigest()
        locked = {"source": "GOOGLE_DOCS", "report_id": "2026-10-09_08-00", "body_hash": body_hash,
                  "source_file_id": "doc-test", "source_revision_id": "revision-test",
                  "source_created_at": "2026-10-09T14:48:01.144Z",
                  "source_updated_at": "2026-10-09T15:05:07.921Z"}
        structured = {"full_text": body, "facts": [
            {"section": "今日の主導市場", "text": leadership, "source_excerpt": "今日の主導市場\n" + leadership},
            {"section": "重要ニュース・イベント", "text": news, "source_excerpt": "重要ニュース・イベント\n" + news},
            {"section": "結論", "text": conclusion, "source_excerpt": "結論\n" + conclusion},
        ]}

        candidate = prepare_candidate(body, locked, structured)
        sections = {section["section_id"]: section["fact_ids"] for section in candidate["sections"]}
        facts = {fact["fact_id"]: fact for fact in candidate["structured_facts"]}
        self.assertTrue(candidate["source_snapshot_id"].startswith("docs-revision-sha256:"))
        self.assertEqual(body_hash, candidate["source_snapshot_identity"]["body_hash"])
        snapshot = candidate["market_data_snapshot"]
        self.assertEqual("SOURCE_RECONSTRUCTED", snapshot["snapshot_provenance"])
        self.assertEqual("2026-10-09T08:00:00+09:00", snapshot["report_as_of"])
        self.assertEqual(locked["source_created_at"], snapshot["source_document_created_at"])
        self.assertEqual(locked["source_updated_at"], snapshot["source_document_updated_at"])
        self.assertEqual(body_hash, snapshot["source_body_sha256"])
        attention = facts[sections["attention_points"][0]]
        self.assertEqual(leadership, attention["text"])
        headline = facts[sections["news_materials"][0]]
        self.assertEqual("AI投資収益性への懸念", headline["fields"]["headline"])
        self.assertIn(news, headline["source_excerpt"])
        overall = facts[sections["overall_judgement"][0]]
        self.assertEqual("慎重姿勢が優勢", overall["text"])
        self.assertIn(overall["text"], overall["source_excerpt"])


if __name__ == "__main__":
    unittest.main()
