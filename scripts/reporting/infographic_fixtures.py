"""Clearly synthetic, source-complete fixtures for the four formal layouts."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .infographic_renderer import TEMPLATE_CONFIG

FIXTURE_DATE = "2026-10-09"
MARKET_VALUES = (
    ("金", "Gold", "101.25", "fixture-USD/oz", "07:58 JST", "中立", "原油安は支え / 金利上昇なら弱気"),
    ("WTI原油", "WTI", "88.40", "fixture-USD/bbl", "07:58 JST", "中立", "供給不安は強気 / 需要減速なら弱気"),
    ("日経225先物", "Nikkei 225 Futures (OSE)", "39012.50", "fixture-points", "07:58 JST", "中立", "夜間の買い維持で強気 / 米株先物安で弱気"),
    ("USD/JPY", "USD/JPY", "149.35", "fixture-JPY/USD", "07:58 JST", "中立", "米金利上昇なら上向き / 円買い再開で下向き"),
    ("EUR/USD", "EUR/USD", "1.1042", "fixture-USD/EUR", "07:58 JST", "中立", "ドル一服なら上向き / 欧州指標悪化で下向き"),
    ("BTCUSD", "BTCUSD", "61234.50", "fixture-USD/BTC", "07:58 JST", "中立", "株高継続なら支え / リスク回避再燃で弱気"),
)

TIMELINE_CONTENT = {
    "08:00": [
        "07:00 | 米金利低下 | 債券買い | 株の下支え",
        "07:15 | 米株先物反発 | 大型株が回復 | 売り一巡を確認",
        "07:30 | 原油は横ばい | 供給材料を消化 | インフレ警戒は残る",
        "07:45 | 金は小幅高 | ドル一服 | 安全需要が支え",
        "08:00 | 東京へ引き継ぎ | 金利とAI株が焦点 | 寄り後に確認",
    ],
    "12:00": [
        "08:00 | 朝の前提 | 金利と大型株を注視 | シナリオを固定",
        "09:00 | 寄り付き | 指数は弱含み | 大型株に売り",
        "09:30 | 半導体株が反発 | 銘柄差が拡大 | 指数を下支え",
        "10:30 | breadth改善 | 値上がり優勢 | 全面安ではない",
        "11:30 | 前引け | 下げ幅縮小 | 後場で継続確認",
        "12:00 | 判断更新 | 選別的な底堅さ | 午後へ引継ぎ",
    ],
    "16:00": [
        "09:00 | 寄り付き | 売り先行 | 前夜の警戒を反映",
        "10:00 | 前場中盤 | 主力株に売り | breadthは底堅い",
        "11:30 | 前引け | 指数は下落 | 値動きに銘柄差",
        "12:30 | 後場寄り | 買い戻し開始 | 先物主導",
        "14:00 | 後場中盤 | 上昇銘柄が拡大 | 指数を下支え",
        "15:30 | 大引け | 下げ幅を縮小 | 東京時間は回復",
    ],
    "21:00": [
        "16:00 | 東京引け | 選別的な回復 | 欧州初動を待つ",
        "17:00 | 欧州寄り | 株価はまちまち | 金利を確認",
        "18:00 | EUR/USD | 小幅変動 | ドル全面高ではない",
        "19:00 | 欧州債券 | 利回りは横ばい | 金利材料は限定的",
        "20:00 | 米株先物 | 小幅高 | AI関連の選別続く",
        "21:00 | NY開始前 | 原油・金利・半導体 | 初動を確認",
    ],
}

SECTION_CONTENT = {
    "08:00": [
        "主要株価指数は前営業日の終値で比較する / 為替・商品は各取得時刻を併記する",
        "", "米金利の落ち着きが株式を支える / AI関連株の反応でリスク選好を判定",
        "原油の供給懸念 → インフレ警戒 → 金利上昇圧力 → 株式の重し",
        "金利動向が主導 / 半導体株の幅広さを次に確認",
        "金利は低下基調 / 為替は方向感に乏しい / センチメントは中立",
        "日経225は合成fixtureの評価帯で中立 / 実在の指数水準ではない",
        "", "イベント前は発表時刻と予想差を確認 / 値動きとの関係を記録",
        "ドル高一服 → 金を支援 / 原油横ばい → インフレ懸念は残存",
        "東京寄り後の金利・半導体・breadthを照合する",
        "金利再上昇と半導体株安が同時に起きないか",
        "金利安定と半導体株反発が続けば、押し目買いが優勢",
        "米金利低下と幅広い株高が確認されれば、リスク選好が改善",
        "金利急反発、原油高、主力株安が重なれば下振れを警戒",
        "合成fixtureの想定では中立。実市場の判断には使わない",
    ],
    "12:00": [
        "08:00の金利安定シナリオは維持 / 大型株の売りと市場内部を分けて確認",
        "",
        "日経225は弱含み / TOPIXは相対的に底堅い / 値上がり銘柄が優勢",
        "AI関連は銘柄ごとに強弱 / 半導体の反発が指数を下支え",
        "仲値前後はドル需要を確認 / 一方向の円安とは判定しない",
        "債券利回りは小幅変動 / 株価反応との同時性を確認",
        "原油は横ばい / 金は小幅高 / 取得時刻を混同しない",
        "指数安とbreadth改善が併存 / 大型株主導の下落と整合",
        "ドル一服 → 金を支援 / 原油横ばい → インフレ懸念は残る",
        "先物・売買代金の実測なし / 建玉の推定は行わない",
        "",
        "午後は主力株の戻りとbreadth継続を確認",
        "欧州株・金利・EUR/USDへ引き継ぐ",
        "breadthが保たれれば下げ止まり、主力株の戻りを試す",
        "上振れは半導体反発 / 下振れは金利上昇と指数安の再加速",
        "前場は選別的に底堅い。後場の継続確認が必要",
    ],
    "16:00": [
        "朝の売りから回復 / 指数より市場内部の改善を重視",
        "",
        "12:00時点より下げ幅縮小 / TOPIX・breadthは相対的に堅調",
        "値上がり銘柄が広がる / 指数寄与の大きい銘柄は選別",
        "ドル円は小幅変動 / 水準と観測時刻を分けて表示",
        "金利は方向感限定 / 欧米時間の再評価待ち",
        "原油横ばい / 金小幅高 / BTCはリスク選好を確認",
        "主力株の買い戻し → 指数下げ幅縮小 / 全銘柄一様ではない",
        "金利安定 → 株式の下支え / 直接の資金移動量は未観測",
        "当日建玉の確定値なし / 需給の推測は行わない",
        "",
        "欧州初動は株価と国債利回りの反応を照合",
        "NYでは米金利・半導体・原油を追う",
        "東京の回復が続き、金利急変がなければ選別的なリスク選好",
        "金利急反発と主力株売り再開が崩れる条件",
        "大引けに回復。海外時間で持続性を確認",
    ],
    "21:00": [
        "欧州時間は方向まちまち / NY開始前は米金利と先物が焦点",
        "",
        "16:00時点から大きな方向変化なし / 材料の強弱を再点検",
        "米株先物は小幅高 / 半導体の選別が続く",
        "米金利は小動き / 急変がなければ株の支援要因",
        "USD/JPYは横ばい / EUR/USDも小幅変動",
        "金は底堅い / 原油横ばい / 供給材料を継続確認",
        "BTCは中立圏 / 米株先物との同方向性を確認",
        "米金利安定 → 株の下支え / 原油横ばい → インフレ懸念は限定",
        "リスク選好は限定的 / 実フローは未観測",
        "建玉の同時刻データなし / 数量を推定しない",
        "米景況感指標の発表を待つ / 結果と金利反応を確認",
        "",
        "米金利が安定し先物高なら、選別的な買いが続く",
        "金利急上昇と半導体先物安が同時なら下振れ",
        "NY初動を確認し、次の東京時間へ条件を引き継ぐ",
    ],
}


def build_synthetic_fixture(slot: str) -> dict:
    if slot not in TEMPLATE_CONFIG["templates"]:
        raise ValueError("unsupported slot")
    if slot == "08:00":
        from .infographic_0800_fixtures import build_synthetic_0800_source

        return build_synthetic_0800_source()
    template = TEMPLATE_CONFIG["templates"][slot]
    report_id = f"{FIXTURE_DATE}_{slot.replace(':', '-')}"
    weekday = "金"
    title = f"マーケットレポート｜2026/10/09（金）{slot}"
    headline = f"{slot} 時間帯別テンプレート・構造確認"
    facts = []
    sections = []
    text_lines = [title, headline]
    numeric_registry = []

    for index, section_spec in enumerate(template["sections"]):
        section_id, section_title, importance, _ = section_spec
        text_lines.append(section_title)
        fact_ids = []
        if section_id == "market_outlooks":
            for label, market, value, unit, as_of, direction, rationale in MARKET_VALUES:
                fact_id = f"fact:{report_id}:market:{market}"
                text = f"{label} | {direction} | {value} {unit} as of {as_of} | {rationale}"
                fact = {"fact_id": fact_id, "section": section_id, "text": text,
                        "value": value, "unit": unit, "as_of": as_of,
                        "source_excerpt": text, "importance": "CRITICAL",
                        "instrument": market, "label": label, "direction": direction}
                facts.append(fact)
                fact_ids.append(fact_id)
                text_lines.append(text)
                numeric_registry.append({"fact_id": fact_id, "instrument": market, "value": value,
                                         "unit": unit, "as_of": as_of, "source_excerpt": text})
        elif section_spec[3] == "timeline":
            for event_index, text in enumerate(TIMELINE_CONTENT[slot], start=1):
                fact_id = f"fact:{report_id}:{section_id}:{event_index}"
                facts.append({"fact_id": fact_id, "section": section_id, "text": text,
                              "source_excerpt": text, "importance": importance})
                fact_ids.append(fact_id)
                text_lines.append(text)
        else:
            text = SECTION_CONTENT[slot][index]
            if not text:
                raise ValueError(f"missing synthetic content {slot} {section_id}")
            fact_id = f"fact:{report_id}:{section_id}:1"
            facts.append({"fact_id": fact_id, "section": section_id, "text": text,
                          "source_excerpt": text, "importance": importance})
            fact_ids.append(fact_id)
            text_lines.append(text)
        sections.append({"section_id": section_id, "fact_ids": fact_ids})

    full_text = "\n".join(text_lines)
    body_hash = hashlib.sha256(full_text.encode("utf-8")).hexdigest()
    all_fact_map = {fact["fact_id"]: fact for fact in facts}
    by_section = {section["section_id"]: [all_fact_map[fact_id] for fact_id in section["fact_ids"]]
                  for section in sections}

    def values(section_id):
        return [{"fact_id": fact["fact_id"], "text": fact["text"]} for fact in by_section[section_id]]

    section_names = [row[0] for row in template["sections"]]
    timeline_id = next(name for name in section_names if "timeline" in name)
    market_section = by_section["market_outlooks"]
    outlooks = [{"fact_id": fact["fact_id"], "instrument": fact["instrument"],
                 "direction": fact["direction"], "price": fact["value"], "unit": fact["unit"],
                 "as_of": fact["as_of"], "rationale": fact["text"].split(" | ", 3)[3],
                 "bullish_condition": fact["text"].split(" | ", 3)[3],
                 "bearish_condition": fact["text"].split(" | ", 3)[3]} for fact in market_section]

    def first_with(fragment):
        matching = next((name for name in section_names if fragment in name), section_names[0])
        return values(matching)

    return {
        "report_id": report_id, "report_date": FIXTURE_DATE, "report_time": slot,
        "weekday": weekday, "title": title, "headline": headline,
        "overall_judgement": first_with("summary") if slot != "08:00" else values("theme"),
        "body_hash": body_hash, "full_text": full_text,
        "snapshot_id": f"synthetic-snapshot-{body_hash[:16]}",
        "source_snapshot": {"snapshot_id": f"synthetic-snapshot-{body_hash[:16]}",
                            "source": "fixture-only", "market_data_status": "SYNTHETIC"},
        "market_theme": first_with("theme") if slot == "08:00" else first_with("main_scenario"),
        "market_summary": values(section_names[0]),
        "session_timeline": values(timeline_id),
        "drivers": values(section_names[3]),
        "supportive_factors": [{"fact_id": f["fact_id"], "text": f["text"]} for f in facts if any(w in f["text"] for w in ("支援", "下支え", "買い戻し"))],
        "risk_factors": [{"fact_id": f["fact_id"], "text": f["text"]} for f in facts if any(w in f["text"] for w in ("警戒", "弱気", "下振れ", "リスク"))],
        "rates": first_with("rates") if any("rates" in name for name in section_names) else first_with("us_rates"),
        "fx": first_with("fx") if "fx" in section_names else first_with("rates_fx_sentiment"),
        "sentiment": values(section_names[0]),
        "cross_asset_flow": first_with("cross_asset_flow"),
        "positioning": first_with("positioning"),
        "valuation": first_with("valuation") if "valuation" in section_names else [],
        "events": first_with("events") if "events" in section_names else [],
        "market_outlooks": outlooks,
        "main_scenario": values(next(name for name in section_names if "main_scenario" in name or "ny_scenario" in name)),
        "upside_scenario": values("upside_scenario") if "upside_scenario" in section_names else [],
        "downside_scenario": values("downside_scenario") if "downside_scenario" in section_names else [],
        "break_conditions": values("break_conditions") if "break_conditions" in section_names else [],
        "handover": values(section_names[-2]) if len(section_names) >= 2 else [],
        "key_conditions": values("key_conditions") if "key_conditions" in section_names else [],
        "conclusion": values(section_names[-1]),
        "facts": facts, "sections": sections, "numeric_registry": numeric_registry,
        "synthetic_fixture": True,
    }


def save_fixture_json(slot: str, destination: str | Path) -> Path:
    fixture = build_synthetic_fixture(slot)
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(fixture, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path
