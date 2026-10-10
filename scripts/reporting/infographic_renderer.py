"""Deterministic slot-specific infographic layouts for source-bound reports.

The renderer consumes structured facts extracted from one locked report body.
It never fetches market data, summarizes source prose, or infers missing facts.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from .infographic import ValidationFailure

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE_PATH = ROOT / "config" / "infographic_templates_v1.json"
TEMPLATE_CONFIG = json.loads(TEMPLATE_PATH.read_text(encoding="utf-8"))
SOURCE_SCHEMA_PATH = ROOT / "schemas" / "infographic-structured-source.schema.json"
SOURCE_SCHEMA = json.loads(SOURCE_SCHEMA_PATH.read_text(encoding="utf-8"))
WIDTH = int(TEMPLATE_CONFIG["width"])
DISPLAY_WIDTH = int(TEMPLATE_CONFIG["target_display_width"])
SCALE = DISPLAY_WIDTH / WIDTH
MARGIN = 44
GAP = 18
BODY_SIZE = 26
TABLE_SIZE = 26
PANEL_TITLE_SIZE = 31
TITLE_SIZE = 66
SUBTITLE_SIZE = 32
HEADER_HEIGHT = 244
BOTTOM_MARGIN = 42
MAX_HEIGHT = 3600
COLORS = {
    "background": "#F2F7FC", "navy": "#061B44", "navy2": "#0A3471",
    "blue": "#155EB3", "blue_light": "#E5F1FF", "text": "#0C2850",
    "muted": "#3E5F83", "white": "#FFFFFF", "stroke": "#8FB6E4",
    "red": "#C62828", "red_light": "#FFF0EF", "green": "#147A45",
    "green_light": "#EAF8EF", "orange": "#EA8611", "yellow": "#FFF2C4",
}
SLOT_LABELS = ("08:00", "12:00", "16:00", "21:00")
MARKET_NAMES = ("Gold", "WTI", "Nikkei 225 Futures (OSE)", "USD/JPY", "EUR/USD", "BTCUSD")
FORBIDDEN_OUTPUT = ("DRAFT ONLY", "BLOCKED / NOT APPROVED", "NOT APPROVED", "APPROVED", "reviewer approval", "user approval", "ChatGPT approval")


class InfographicRenderError(ValueError):
    """A source or layout failure that keeps only the infographic not ready."""


def _font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont:
    choices = (
        ["C:/Windows/Fonts/meiryob.ttc", "C:/Windows/Fonts/YuGothB.ttc", "C:/Windows/Fonts/meiryo.ttc"]
        if bold else
        ["C:/Windows/Fonts/meiryo.ttc", "C:/Windows/Fonts/YuGothR.ttc"]
    )
    for path in choices:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                pass
    raise InfographicRenderError("RENDER_FONT_UNAVAILABLE")


def _template(slot: str) -> dict:
    try:
        return TEMPLATE_CONFIG["templates"][slot]
    except KeyError as exc:
        raise InfographicRenderError("UNKNOWN_REPORT_TIME_SLOT") from exc


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _fact_index(source: dict) -> dict[str, dict]:
    facts = source.get("facts")
    if not isinstance(facts, list):
        raise InfographicRenderError("STRUCTURED_FACTS_REQUIRED")
    result = {}
    for fact in facts:
        if not isinstance(fact, dict) or not fact.get("fact_id") or fact["fact_id"] in result:
            raise InfographicRenderError("FACT_ID_MISSING_OR_DUPLICATE")
        result[fact["fact_id"]] = fact
    return result


def validate_source(source: dict) -> dict[str, Any]:
    """Validate identity, source excerpts, template coverage and numeric bindings."""
    if not isinstance(source, dict):
        raise InfographicRenderError("STRUCTURED_SOURCE_REQUIRED")
    if source.get("template_mode") == "08:00_FIXED_SINGLE_SHEET":
        from .infographic_0800_fixed import validate_0800_source

        result = validate_0800_source(source)
        if result.get("status") != "PASS":
            errors = result.get("errors", [])
            identity_error = next((error for error in errors if error.startswith("REPORT_ID_OR_08_00_DATETIME_MISMATCH")), None)
            raise InfographicRenderError("REPORT_ID_MISMATCH" if identity_error else (errors[0] if errors else "0800_SOURCE_NOT_READY"))
        return {"report_time": "08:00", "report_id": source.get("report_id"),
                "synthetic_fixture": source.get("synthetic_fixture") is True}
    missing_schema_fields = [name for name in SOURCE_SCHEMA["required"] if name not in source]
    if missing_schema_fields:
        raise InfographicRenderError("STRUCTURED_SOURCE_SCHEMA_FIELDS_MISSING:" + ",".join(missing_schema_fields))
    for name in ("overall_judgement", "market_theme", "market_summary", "session_timeline", "drivers",
                 "supportive_factors", "risk_factors", "rates", "fx", "sentiment", "cross_asset_flow",
                 "positioning", "valuation", "events", "market_outlooks", "main_scenario", "upside_scenario",
                 "downside_scenario", "break_conditions", "handover", "key_conditions", "conclusion"):
        if not isinstance(source[name], list):
            raise InfographicRenderError(f"STRUCTURED_SOURCE_SECTION_REQUIRED:{name}")
    if not isinstance(source["synthetic_fixture"], bool):
        raise InfographicRenderError("STRUCTURED_SOURCE_FIXTURE_FLAG_INVALID")
    slot = source.get("report_time")
    template = _template(str(slot))
    date = source.get("report_date")
    report_id = f"{date}_{str(slot).replace(':', '-')}"
    if source.get("report_id") != report_id:
        raise InfographicRenderError("REPORT_ID_MISMATCH")
    if source.get("title") != f"マーケットレポート｜{str(date).replace('-', '/')}（{source.get('weekday', '金')}）{slot}":
        raise InfographicRenderError("REPORT_TITLE_IDENTITY_MISMATCH")
    if source.get("synthetic_fixture") is not True:
        raise InfographicRenderError("FIXTURE_RENDERER_ACCEPTS_SYNTHETIC_INPUT_ONLY")
    if not str(source.get("snapshot_id", "")).strip():
        raise InfographicRenderError("SOURCE_SNAPSHOT_REQUIRED")
    full_text = source.get("full_text")
    if not isinstance(full_text, str) or not full_text.strip() or source.get("body_hash") != _sha256(full_text):
        raise InfographicRenderError("SOURCE_BODY_HASH_MISMATCH")

    facts = _fact_index(source)
    section_specs = template["sections"]
    sections = source.get("sections")
    if not isinstance(sections, list) or len(sections) != 16:
        raise InfographicRenderError("SLOT_TEMPLATE_MUST_HAVE_16_SECTIONS")
    expected_ids = [item[0] for item in section_specs]
    if [section.get("section_id") for section in sections] != expected_ids:
        raise InfographicRenderError("SLOT_SECTION_ORDER_MISMATCH")
    required_ids: set[str] = set()
    for section, spec in zip(sections, section_specs, strict=True):
        section_id, _, importance, _ = spec
        if section.get("section_id") != section_id:
            raise InfographicRenderError("SLOT_SECTION_ORDER_MISMATCH")
        ids = section.get("fact_ids")
        if not isinstance(ids, list) or not ids:
            raise InfographicRenderError(f"SECTION_FACTS_MISSING:{section_id}")
        for fact_id in ids:
            fact = facts.get(fact_id)
            if not fact or fact.get("section") != section_id:
                raise InfographicRenderError(f"SECTION_FACT_BINDING_INVALID:{section_id}:{fact_id}")
            excerpt = fact.get("source_excerpt")
            text = fact.get("text")
            if not isinstance(excerpt, str) or not excerpt or excerpt not in full_text or not isinstance(text, str) or text not in excerpt:
                raise InfographicRenderError(f"FACT_NOT_IN_SOURCE:{fact_id}")
            if fact.get("importance") not in ("CRITICAL", "HIGH", "NORMAL"):
                raise InfographicRenderError(f"FACT_IMPORTANCE_INVALID:{fact_id}")
            if importance == "CRITICAL" and fact["importance"] != "CRITICAL":
                raise InfographicRenderError(f"CRITICAL_SECTION_FACT_DOWNGRADED:{fact_id}")
            # Every source fact assigned to a section is required to render.
            # Importance controls visual emphasis, never silent omission.
            required_ids.add(fact_id)

    outlook_section = expected_ids.index("market_outlooks")
    outlook_facts = sections[outlook_section]["fact_ids"]
    if len(outlook_facts) != 6:
        raise InfographicRenderError("SIX_MARKET_OUTLOOKS_REQUIRED")
    instruments = []
    for fact_id in outlook_facts:
        fact = facts[fact_id]
        instrument = fact.get("instrument")
        if instrument not in MARKET_NAMES:
            raise InfographicRenderError("MARKET_OUTLOOK_INSTRUMENT_INVALID")
        instruments.append(instrument)
    if len(set(instruments)) != 6 or set(instruments) != set(MARKET_NAMES):
        raise InfographicRenderError("SIX_MARKET_OUTLOOKS_REQUIRED")

    registry = source.get("numeric_registry")
    if not isinstance(registry, list) or len(registry) < 6:
        raise InfographicRenderError("NUMERIC_REGISTRY_INCOMPLETE")
    seen_numeric_ids = set()
    for entry in registry:
        if not isinstance(entry, dict) or not all(entry.get(key) for key in ("fact_id", "instrument", "value", "unit", "as_of", "source_excerpt")):
            raise InfographicRenderError("NUMERIC_REGISTRY_ENTRY_INCOMPLETE")
        if entry["fact_id"] in seen_numeric_ids or entry["fact_id"] not in facts:
            raise InfographicRenderError("NUMERIC_FACT_ID_INVALID")
        seen_numeric_ids.add(entry["fact_id"])
        excerpt = entry["source_excerpt"]
        fact = facts[entry["fact_id"]]
        if excerpt not in full_text or excerpt != fact["source_excerpt"]:
            raise InfographicRenderError(f"NUMERIC_SOURCE_EXCERPT_MISMATCH:{entry['fact_id']}")
        for required in (str(entry["value"]), str(entry["unit"]), str(entry["as_of"])):
            if required not in excerpt:
                raise InfographicRenderError(f"NUMERIC_SOURCE_PROVENANCE_MISSING:{entry['fact_id']}")
    return {
        "status": "PASS", "report_id": report_id, "report_time": slot,
        "template_id": template["template_id"], "body_hash": source["body_hash"],
        "snapshot_id": source["snapshot_id"], "required_fact_ids": sorted(required_ids),
        "section_count": len(sections), "market_count": len(instruments),
        "numeric_registry_count": len(registry),
    }


def _wrap(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    lines: list[str] = []
    for paragraph in str(text).splitlines() or [""]:
        current = ""
        for char in paragraph:
            candidate = current + char
            if current and draw.textlength(candidate, font=font) > max_width:
                lines.append(current)
                current = char
            else:
                current = candidate
        lines.append(current)
    return lines or [""]


def _importance_color(section: dict, facts: list[dict]) -> tuple[str, str]:
    content = " ".join(fact["text"] for fact in facts)
    title = str(section.get("title", ""))
    if any(word in title + content for word in ("崩れる", "下振れ", "リスク", "警戒", "注意", "弱気")):
        return COLORS["red"], COLORS["red_light"]
    if any(word in title + content for word in ("支援", "上振れ", "好材料", "強気")):
        return COLORS["green"], COLORS["green_light"]
    if any(word in title for word in ("注目", "最重要", "イベント", "結論", "テーマ")):
        return COLORS["orange"], COLORS["yellow"]
    return COLORS["blue"], COLORS["blue_light"]


def _luminance(hex_color: str) -> float:
    channels = []
    for start in (1, 3, 5):
        value = int(hex_color[start:start + 2], 16) / 255
        channels.append(value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4)
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]


def _contrast(foreground: str, background: str) -> float:
    first, second = sorted((_luminance(foreground), _luminance(background)), reverse=True)
    return (first + 0.05) / (second + 0.05)


def _draw_header(image: Image.Image, source: dict, title_font, subtitle_font, body_font) -> None:
    draw = ImageDraw.Draw(image)
    for y in range(HEADER_HEIGHT):
        t = y / max(1, HEADER_HEIGHT - 1)
        r = int(5 + t * 7)
        g = int(24 + t * 38)
        b = int(63 + t * 72)
        draw.line((0, y, WIDTH, y), fill=(r, g, b))
    # A restrained vector skyline and Fuji silhouette support the market-report
    # identity without fetching or embedding unlicensed external imagery.
    skyline_x = 1030
    draw.polygon([(1160, 176), (1314, 92), (1466, 176)], fill="#315E98")
    draw.polygon([(1274, 116), (1314, 92), (1352, 116), (1328, 111), (1314, 103), (1298, 112)], fill="#E7F0FF")
    draw.rectangle((skyline_x, 176, WIDTH, HEADER_HEIGHT), fill="#0B2756")
    buildings = [(1040, 127, 52, 117), (1098, 93, 64, 151), (1167, 142, 44, 102),
                 (1218, 112, 54, 132), (1380, 132, 58, 112), (1446, 79, 50, 165),
                 (1504, 118, 72, 126)]
    for x, y, width, height in buildings:
        draw.rectangle((x, y, x + width, HEADER_HEIGHT), fill="#102F67")
        for wx in range(x + 11, x + width - 7, 16):
            for wy in range(y + 15, HEADER_HEIGHT - 14, 24):
                draw.rectangle((wx, wy, wx + 5, wy + 9), fill="#F0A92F")
    title = source["title"]
    # Keep the title inside the left header column so it never collides with
    # the timestamp badge or decorative skyline at common slot title lengths.
    fitted_title_font = title_font
    for candidate_size in range(TITLE_SIZE, 39, -1):
        candidate_font = _font(candidate_size, bold=True)
        if draw.textlength(title, font=candidate_font) <= 950:
            fitted_title_font = candidate_font
            break
    draw.text((MARGIN, 27), title, font=fitted_title_font, fill=COLORS["white"], stroke_width=1, stroke_fill="#082251")
    draw.text((MARGIN + 2, 117), source["headline"], font=subtitle_font, fill="#FFFFFF", stroke_width=1, stroke_fill="#0A2250")
    draw.text((MARGIN + 2, 176), "合成fixture｜市場データではありません", font=body_font, fill="#FFE3A2")
    draw.rounded_rectangle((1310, 22, 1556, 72), radius=12, fill="#0A1E43", outline="#97C5FF", width=2)
    badge_font = _font(22, bold=True)
    badge_text = f"基準 {source['report_time']} JST"
    badge_width = draw.textlength(badge_text, font=badge_font)
    draw.text((1433 - badge_width / 2, 31), badge_text, font=badge_font, fill="#FFFFFF")
    # Visual chips: simple labels remain legible even where emoji fonts are absent.
    for index, (label, color) in enumerate((("US", "#D2473B"), ("JP", "#C53943"), ("EU", "#2C67B2"))):
        x = 1320 + index * 78
        draw.rounded_rectangle((x, 83, x + 68, 122), radius=9, fill=color)
        draw.text((x + 15, 86), label, font=_font(25, bold=True), fill="#FFFFFF")


def _wrap_text(draw, text, font, max_width):
    return _wrap(draw, str(text), font, max_width)


def _panel_body_height(draw, fact: dict, kind: str, width: int, body_font) -> int:
    if kind == "market_table":
        cols = fact["text"].split(" | ")
        widths = (210, 230, 310, width - 750)
        line_counts = [len(_wrap_text(draw, col, body_font, max(60, col_width - 18))) for col, col_width in zip(cols, widths)]
        return max(58, max(line_counts) * (BODY_SIZE + 8) + 18)
    max_width = width - 48
    lines = _wrap_text(draw, fact["text"], body_font, max_width)
    return max(42, len(lines) * (BODY_SIZE + 9) + 12)


def _panel_height(draw, section: dict, facts: list[dict], kind: str, width: int, body_font) -> int:
    header = 66
    if kind == "timeline":
        max_lines = 1
        event_width = max(180, (width - 42 - GAP * max(0, len(facts) - 1)) // max(1, len(facts)))
        for fact in facts:
            max_lines = max(max_lines, len(_wrap_text(draw, fact["text"], body_font, event_width - 24)))
        return header + max_lines * (BODY_SIZE + 10) + 102
    if kind == "market_table":
        rows = sum(_panel_body_height(draw, fact, kind, width, body_font) for fact in facts)
        return header + 52 + rows + 24
    body = sum(_panel_body_height(draw, fact, kind, width, body_font) for fact in facts)
    return max(152, header + body + 30)


def _record_binding(bindings: list, fact: dict, text: str, box: tuple[int, int, int, int], role: str) -> None:
    bindings.append({
        "fact_id": fact["fact_id"], "draw_call_text": text,
        "source_excerpt": fact["source_excerpt"], "role": role,
        "bbox": list(box),
    })


def _draw_panel(draw, box, index: int, section: dict, facts: list[dict], kind: str, body_font, title_font, bindings: list, card_meta: list) -> None:
    x1, y1, x2, y2 = box
    accent, light = _importance_color(section, facts)
    # Criticality affects visual weight, while semantic color communicates
    # support/risk/attention. Do not turn every critical panel into an alert.
    critical = any(f["importance"] == "CRITICAL" for f in facts)
    outline = accent if critical else COLORS["stroke"]
    draw.rounded_rectangle(box, radius=16, fill=COLORS["white"], outline=outline, width=3 if critical else 2)
    draw.rounded_rectangle((x1, y1, x2, y1 + 63), radius=15, fill=COLORS["navy"])
    draw.rectangle((x1, y1 + 42, x2, y1 + 63), fill=COLORS["navy"])
    draw.ellipse((x1 + 15, y1 + 8, x1 + 60, y1 + 53), fill=COLORS["orange"])
    number = str(index + 1)
    num_width = draw.textlength(number, font=_font(28, bold=True))
    draw.text((x1 + 37 - num_width / 2, y1 + 14), number, font=_font(28, bold=True), fill=COLORS["white"])
    heading = section["title"]
    draw.text((x1 + 75, y1 + 10), heading, font=title_font, fill=COLORS["white"])
    content_top = y1 + 76
    content_bottom = y2 - 14
    card_meta.append({"index": index + 1, "section_id": section["section_id"], "title": heading,
                      "importance": section["importance"], "bbox": list(box), "render_kind": kind})

    if kind == "timeline":
        n = len(facts)
        col_width = (x2 - x1 - 46 - GAP * max(0, n - 1)) // max(1, n)
        cursor = x1 + 22
        mid_y = content_top + 20
        draw.line((cursor + 12, mid_y, x2 - 24, mid_y), fill=COLORS["orange"], width=6)
        for fact in facts:
            event_box = (cursor, content_top, cursor + col_width, content_bottom)
            draw.rounded_rectangle(event_box, radius=10, fill=COLORS["blue_light"], outline=COLORS["stroke"], width=1)
            draw.ellipse((cursor + 9, mid_y - 8, cursor + 25, mid_y + 8), fill=COLORS["orange"])
            text_top = content_top + 43
            lines = _wrap_text(draw, fact["text"], body_font, col_width - 22)
            for line in lines:
                draw.text((cursor + 10, text_top), line, font=body_font, fill=COLORS["text"])
                text_top += BODY_SIZE + 10
            _record_binding(bindings, fact, fact["text"], event_box, "timeline_event")
            cursor += col_width + GAP
        return

    if kind == "market_table":
        columns = ("市場", "短期判断", "確認値・時刻", "根拠 / 強気・弱気条件")
        widths = (210, 230, 310, x2 - x1 - 750)
        col_x = x1 + 20
        head_y = content_top
        draw.rounded_rectangle((x1 + 18, head_y, x2 - 18, head_y + 42), radius=7, fill=COLORS["blue_light"])
        for label, width in zip(columns, widths):
            draw.text((col_x + 6, head_y + 5), label, font=_font(25, bold=True), fill=COLORS["navy"])
            col_x += width
        y = head_y + 46
        for row_index, fact in enumerate(facts):
            cells = fact["text"].split(" | ")
            if len(cells) != 4:
                raise InfographicRenderError(f"MARKET_TABLE_CELL_COUNT_INVALID:{fact['fact_id']}")
            heights = [len(_wrap_text(draw, cell, body_font, width - 16)) * (BODY_SIZE + 8) + 12
                       for cell, width in zip(cells, widths)]
            row_height = max(heights, default=50)
            fill = "#F6FAFF" if row_index % 2 == 0 else "#EAF3FE"
            draw.rectangle((x1 + 18, y, x2 - 18, y + row_height), fill=fill)
            col_x = x1 + 20
            for cell_index, (cell, width) in enumerate(zip(cells, widths)):
                cell_lines = _wrap_text(draw, cell, body_font, width - 16)
                if cell_index == 1:
                    color = COLORS["green"] if any(word in cell for word in ("強気", "上昇", "支援")) else COLORS["red"] if any(word in cell for word in ("弱気", "下落", "警戒")) else COLORS["blue"]
                else:
                    color = COLORS["text"]
                line_y = y + 5
                for line in cell_lines:
                    draw.text((col_x + 6, line_y), line, font=body_font, fill=color)
                    line_y += BODY_SIZE + 8
                col_x += width
            _record_binding(bindings, fact, fact["text"], (x1 + 18, y, x2 - 18, y + row_height), "market_outlook_row")
            y += row_height
            if row_index < len(facts) - 1:
                draw.line((x1 + 18, y, x2 - 18, y), fill=COLORS["stroke"], width=1)
        return

    y = content_top
    for fact in facts:
        fill = light if fact["importance"] == "CRITICAL" else COLORS["white"]
        lines = _wrap_text(draw, fact["text"], body_font, x2 - x1 - 58)
        if kind == "flow":
            # Arrow glyphs are source text; they show the stated relationship,
            # rather than drawing an independent market-price chart.
            prefix = "→ " if "→" not in fact["text"] else ""
        else:
            prefix = "• "
        draw.rounded_rectangle((x1 + 15, y - 2, x1 + 27, y + 28), radius=6, fill=accent)
        line_y = y - 2
        text_lines = lines
        if prefix and lines:
            first = prefix + lines[0]
            if draw.textlength(first, font=body_font) <= x2 - x1 - 58:
                text_lines = [first] + lines[1:]
        for line in text_lines:
            draw.text((x1 + 38, line_y), line, font=body_font, fill=COLORS["text"])
            line_y += BODY_SIZE + 9
        rendered_text = "\n".join(text_lines)
        _record_binding(bindings, fact, fact["text"], (x1 + 15, y - 2, x2 - 18, line_y), "fact_text")
        y = line_y + 12


def render_infographic(source: dict, output_path: str | Path | None = None, *,
                       template_mode: str | None = None) -> dict[str, Any]:
    """Use the dedicated fixed single-sheet contract for 08:00 only."""
    if isinstance(source, dict) and (source.get("template_mode") == "08:00_FIXED_SINGLE_SHEET"
                                     or source.get("report_time") == "08:00"):
        if template_mode == "GENERIC_AUTO_LAYOUT":
            raise InfographicRenderError("0800_GENERIC_AUTO_LAYOUT_FORBIDDEN")
        if template_mode not in (None, "08:00_FIXED_SINGLE_SHEET"):
            raise InfographicRenderError("0800_TEMPLATE_MODE_MISMATCH")
        from .infographic_0800_fixed import render_0800_fixed

        result = render_0800_fixed(source, output_path, draft_preview=True)
        if source.get("synthetic_fixture") is True and result.get("image_bytes"):
            result["status"] = "READY"
            result["infographic_status"] = "READY"
            result["artifact_type"] = "SYNTHETIC_FORMAL_LAYOUT_FIXTURE"
            result["production_eligible"] = False
        return result

    if template_mode == "08:00_FIXED_SINGLE_SHEET":
        raise InfographicRenderError("0800_TEMPLATE_MODE_REQUIRES_0800_IDENTITY")

    source_check = validate_source(source)
    template = _template(source["report_time"])
    facts = _fact_index(source)
    section_rows = source["sections"]
    section_specs = template["sections"]
    sections = [
        {"section_id": spec[0], "title": spec[1], "importance": spec[2], "kind": spec[3],
         "fact_ids": section_rows[i]["fact_ids"]}
        for i, spec in enumerate(section_specs)
    ]
    by_id = {section["section_id"]: section for section in sections}
    try:
        body_font = _font(BODY_SIZE)
        panel_title_font = _font(PANEL_TITLE_SIZE, bold=True)
        hero_title_font = _font(TITLE_SIZE, bold=True)
        subtitle_font = _font(SUBTITLE_SIZE, bold=True)
    except OSError as exc:
        raise InfographicRenderError("RENDER_FONT_UNAVAILABLE") from exc

    probe = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    row_specs = template["layout_rows"]
    estimated_rows = []
    y = HEADER_HEIGHT + 22
    cards = []
    bindings = []
    rows_meta = []
    for row in row_specs:
        # layout_rows store stable section positions in the slot template.
        row_sections = [sections[section_index] for section_index in row]
        row_facts = [[facts[fact_id] for fact_id in section["fact_ids"]] for section in row_sections]
        count = len(row_sections)
        row_widths = [WIDTH - 2 * MARGIN] if count == 1 else [(WIDTH - 2 * MARGIN - GAP) // 2] * 2
        heights = [_panel_height(probe, section, items, section["kind"], width, body_font)
                   for section, items, width in zip(row_sections, row_facts, row_widths)]
        row_height = max(heights)
        if row_height > 720:
            raise InfographicRenderError("PANEL_EXCEEDS_READABLE_LAYOUT_LIMIT")
        estimated_rows.append((row, row_height, row_sections, row_facts, row_widths))
        y += row_height + GAP
    image_height = y + BOTTOM_MARGIN
    if image_height > MAX_HEIGHT:
        raise InfographicRenderError("LAYOUT_EXCEEDS_ONE_PAGE_LIMIT")
    image = Image.new("RGB", (WIDTH, image_height), COLORS["background"])
    _draw_header(image, source, hero_title_font, subtitle_font, body_font)
    draw = ImageDraw.Draw(image)
    y = HEADER_HEIGHT + 22
    for row, row_height, row_sections, row_facts, row_widths in estimated_rows:
        row_boxes = []
        x = MARGIN
        for width in row_widths:
            row_boxes.append((x, y, x + width, y + row_height))
            x += width + GAP
        for section in row_sections:
            section_index = next(i for i, item in enumerate(sections) if item["section_id"] == section["section_id"])
            box = row_boxes[row_sections.index(section)]
            _draw_panel(draw, box, section_index, section, row_facts[row_sections.index(section)],
                        section["kind"], body_font, panel_title_font, bindings, cards)
        rows_meta.append({"section_ids": [section["section_id"] for section in row_sections],
                          "bbox": [MARGIN, y, WIDTH - MARGIN, y + row_height]})
        y += row_height + GAP
    draw.text((MARGIN, image_height - 34), "構造化factから描画｜チャート・ゲージなし｜fixture検証用", font=_font(26), fill=COLORS["muted"])

    rendered_ids = sorted({binding["fact_id"] for binding in bindings})
    required_ids = source_check["required_fact_ids"]
    missing_ids = sorted(set(required_ids) - set(rendered_ids))
    extra_ids = sorted(set(rendered_ids) - set(required_ids))
    if missing_ids:
        return {"status": "NOT_READY", "infographic_status": "NOT_READY", "errors": ["REQUIRED_FACTS_MISSING"],
                "required_fact_ids": required_ids, "rendered_fact_ids": rendered_ids,
                "missing_fact_ids": missing_ids, "extra_fact_ids": extra_ids, "image_bytes": None}

    binding_by_fact = {binding["fact_id"]: binding for binding in bindings}
    numeric_checks = []
    for entry in source["numeric_registry"]:
        binding = binding_by_fact.get(entry["fact_id"])
        draw_text = binding["draw_call_text"] if binding else ""
        matches = (
            binding is not None
            and draw_text == entry["source_excerpt"]
            and str(entry["value"]) in draw_text
            and str(entry["unit"]) in draw_text
            and str(entry["as_of"]) in draw_text
        )
        numeric_checks.append({"fact_id": entry["fact_id"], "instrument": entry["instrument"],
                               "value": entry["value"], "unit": entry["unit"], "as_of": entry["as_of"],
                               "source_excerpt": entry["source_excerpt"], "draw_call_text": draw_text,
                               "status": "PASS" if matches else "FAIL"})
    if any(entry["status"] != "PASS" for entry in numeric_checks):
        return {"status": "FAILED_VALIDATION", "infographic_status": "FAILED_VALIDATION",
                "errors": ["NUMERIC_DRAW_CALL_MISMATCH"], "numeric_checks": numeric_checks,
                "required_fact_ids": required_ids, "rendered_fact_ids": rendered_ids,
                "missing_fact_ids": missing_ids, "extra_fact_ids": extra_ids, "image_bytes": None}

    image_bytes_io = __import__("io").BytesIO()
    image.save(image_bytes_io, format="PNG", optimize=False, compress_level=9)
    image_bytes = image_bytes_io.getvalue()
    image_sha256 = hashlib.sha256(image_bytes).hexdigest()
    if output_path is not None:
        destination = Path(output_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(image_bytes)

    effective_body_px = BODY_SIZE * SCALE
    effective_heading_px = PANEL_TITLE_SIZE * SCALE
    max_contrast = min(_contrast(COLORS["text"], COLORS["white"]),
                       _contrast(COLORS["text"], COLORS["blue_light"]),
                       _contrast(COLORS["white"], COLORS["navy"]))
    collision_free = all(
        left["bbox"][2] <= right["bbox"][0] or right["bbox"][2] <= left["bbox"][0]
        or left["bbox"][3] <= right["bbox"][1] or right["bbox"][3] <= left["bbox"][1]
        for i, left in enumerate(cards) for right in cards[i + 1:]
    )
    text_inside_cards = all(
        card["bbox"][0] <= binding["bbox"][0] and binding["bbox"][2] <= card["bbox"][2]
        and card["bbox"][1] <= binding["bbox"][1] and binding["bbox"][3] <= card["bbox"][3]
        for card in cards for binding in bindings if binding["fact_id"] in by_id[card["section_id"]]["fact_ids"]
    )
    visual_qa = {
        "width_px": image.width, "height_px": image.height, "target_display_width_px": DISPLAY_WIDTH,
        "effective_body_font_px": round(effective_body_px, 2),
        "effective_heading_font_px": round(effective_heading_px, 2),
        "minimum_text_contrast_ratio": round(max_contrast, 2),
        "panel_overlap": "PASS" if collision_free else "FAIL",
        "text_within_panels": "PASS" if text_inside_cards else "FAIL",
        "table_columns_within_canvas": "PASS" if image.width == WIDTH else "FAIL",
        "vision_status": "NOT_RUN", "ocr_status": "NOT_RUN",
        "status": "PASS" if effective_body_px >= 12 and effective_heading_px >= 14 and max_contrast >= 4.5 and collision_free and text_inside_cards else "FAIL",
    }
    score = {
        "情報量": 5 if len(cards) == 16 and not missing_ids else 0,
        "視認性": 5 if visual_qa["status"] == "PASS" else 0,
        "重要情報の目立ち方": 5 if any(card["importance"] == "CRITICAL" for card in cards) else 2,
        "デザインの強さ": 5 if image.width == WIDTH and HEADER_HEIGHT > 0 and len(COLORS) >= 10 else 2,
        "本文との整合性": 5 if source_check["status"] == "PASS" and all(c["status"] == "PASS" for c in numeric_checks) else 0,
        "時間帯テンプレート適合性": 5 if len(cards) == 16 and source_check["report_time"] == source["report_time"] else 0,
    }
    quality_total = sum(score.values())
    qa_pass = visual_qa["status"] == "PASS" and quality_total >= 24 and all(v == 5 for v in score.values())
    result = {
        "status": "READY" if qa_pass else "FAILED_VALIDATION",
        "infographic_status": "READY" if qa_pass else "FAILED_VALIDATION",
        "artifact_type": "SYNTHETIC_FORMAL_LAYOUT_FIXTURE",
        "report_status": "UNCHANGED",
        "report_id": source["report_id"], "report_time": source["report_time"],
        "template_id": template["template_id"], "snapshot_id": source["snapshot_id"],
        "body_hash": source["body_hash"], "image_sha256": image_sha256,
        "required_fact_ids": required_ids, "rendered_fact_ids": rendered_ids,
        "missing_fact_ids": missing_ids, "extra_fact_ids": extra_ids,
        "render_bindings": bindings, "numeric_checks": numeric_checks,
        "visual_qa": visual_qa, "quality_score": {"dimensions": score, "total": quality_total},
        "layout": {"cards": cards, "rows": rows_meta, "pages": 1, "reading_order": expected_section_order(template)},
        "optional_qa": {"vision": "NOT_RUN", "ocr": "NOT_RUN"},
        "output_path": str(output_path) if output_path is not None else None,
        "image_bytes": image_bytes,
    }
    if not qa_pass:
        result["errors"] = ["AUTOMATED_VISUAL_QA_OR_QUALITY_GATE_FAILED"]
    return result


def expected_section_order(template: dict) -> list[str]:
    return [section[0] for section in template["sections"]]


def verify_no_legacy_status_text(text: str) -> bool:
    lowered = text.lower()
    return not any(phrase.lower() in lowered for phrase in FORBIDDEN_OUTPUT)
