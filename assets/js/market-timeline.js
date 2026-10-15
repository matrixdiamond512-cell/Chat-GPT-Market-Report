(function attachMarketTimeline(root) {
  const SLOT_DEFINITIONS = Object.freeze({
    "08:00": {
      title: "昨夜のNY市場",
      phases: ["NY開場前", "寄り付き", "序盤", "中盤", "終盤・引け", "東京への引き継ぎ"],
      headings: [/昨夜NY市場の時系列/, /NY市場の時系列/]
    },
    "12:00": {
      title: "東京市場・前場",
      phases: ["寄り付き前", "寄り付き", "前場序盤", "中盤", "前引け"],
      headings: [/東京前場の時系列/, /東京市場.*前場.*時系列/, /前場の時系列/]
    },
    "16:00": {
      title: "東京市場・後場を含む1日",
      phases: ["午前の振り返り", "後場開始", "後場中盤", "大引け", "欧州への引き継ぎ"],
      headings: [/東京市場の時系列/, /東京市場.*時系列/]
    },
    "21:00": {
      title: "欧州市場",
      phases: ["欧州開場前", "寄り付き", "序盤", "中盤", "NYへの引き継ぎ"],
      headings: [/欧州市場.*時系列/, /欧州.*時系列.*反応/]
    }
  });

  const clean = (value) => String(value ?? "").replace(/\s+/g, " ").trim();
  const reportId = (date, time) => `${date}_${String(time || "").replace(":", "-")}`;
  const eventTimestamp = (value) => {
    const match = clean(value).match(/(?:\d{1,2}[/-]\d{1,2}\s*)?\d{1,2}[:：]\d{2}(?:\s*[–—~〜-]\s*\d{1,2}[:：]\d{2})?(?:\s*JST)?/);
    return match ? clean(match[0]) : null;
  };
  const phaseFor = (time, label) => {
    const text = clean(label);
    if (time === "08:00") {
      if (/NY開場前/.test(text)) return "NY開場前";
      if (/寄り付き/.test(text)) return "寄り付き";
      if (/序盤/.test(text)) return "序盤";
      if (/中盤/.test(text)) return "中盤";
      if (/終盤|引け/.test(text) && !/東京/.test(text)) return "終盤・引け";
      if (/東京/.test(text)) return "東京への引き継ぎ";
    }
    if (time === "12:00") {
      if (/寄り付き前/.test(text)) return "寄り付き前";
      if (/寄り付き/.test(text)) return "寄り付き";
      if (/序盤/.test(text)) return "前場序盤";
      if (/中盤/.test(text)) return "中盤";
      if (/前引け/.test(text)) return "前引け";
    }
    if (time === "16:00") {
      if (/午前|前場/.test(text) && /振り返|前引け|序盤|寄り付き/.test(text)) return "午前の振り返り";
      if (/寄り付き前/.test(text)) return "午前の振り返り";
      if (/後場開始|後場序盤|後場.*再開/.test(text)) return "後場開始";
      if (/後場中盤/.test(text)) return "後場中盤";
      if (/大引け/.test(text)) return "大引け";
      if (/欧州/.test(text)) return "欧州への引き継ぎ";
    }
    if (time === "21:00") {
      if (/欧州開場前/.test(text)) return "欧州開場前";
      if (/欧州寄り付き|寄り付き/.test(text)) return "寄り付き";
      if (/欧州序盤|序盤/.test(text)) return "序盤";
      if (/欧州中盤|中盤/.test(text)) return "中盤";
      if (/NY開場前|NYへの引き継ぎ/.test(text)) return "NYへの引き継ぎ";
    }
    return "";
  };

  function parseEventLine(line, time) {
    const text = clean(line);
    if (!text || /改訂追補|この時系列は|以下は.*時系列|まとめ：|結論：/.test(text)) return null;
    if (/未発表|発表予定|発表前/.test(text) && !/発表された|発表後/.test(text)) return null;

    const labels = ["出来事", "反応", "意味", "出典", "次の注目点", "次は"];
    const markerFor = (label) => (label === "次は" ? "次は" : `${label}：`);
    const positions = labels
      .map((label) => ({ label, marker: markerFor(label), index: text.indexOf(markerFor(label)) }))
      .filter((item) => item.index >= 0)
      .sort((a, b) => a.index - b.index);
    const eventIndex = positions.findIndex((item) => item.label === "出来事");
    const reactionIndex = positions.findIndex((item) => item.label === "反応");
    const meaningIndex = positions.findIndex((item) => item.label === "意味");
    if (eventIndex < 0 || reactionIndex < 0 || meaningIndex < 0) return null;

    const valueFor = (label) => {
      const position = positions.findIndex((item) => item.label === label);
      if (position < 0) return "";
      const current = positions[position];
      const valueStart = current.index + current.marker.length;
      const end = positions[position + 1]?.index ?? text.length;
      return clean(text.slice(valueStart, end).replace(/[。；;]$/, ""));
    };
    const prefix = clean(text.slice(0, positions[eventIndex].index).replace(/[｜|／/]$/, ""));
    const phase = phaseFor(time, prefix);
    if (!phase) return null;

    const source = valueFor("出典");
    const reaction = valueFor("反応");
    return {
      phase,
      timeLabel: prefix || "時刻記載なし",
      occurredAt: eventTimestamp(prefix),
      timePrecision: eventTimestamp(prefix) ? "source-stated" : "time-not-recorded",
      reactionObservedAt: eventTimestamp(reaction),
      event: valueFor("出来事"),
      reaction,
      meaning: valueFor("意味"),
      nextWatch: valueFor("次の注目点") || valueFor("次は"),
      sources: source ? [source] : []
    };
  }

  function parseTimelineText(report) {
    const definition = SLOT_DEFINITIONS[report?.time];
    const body = String(report?.fullText || report?.rawText || "").replace(/\r/g, "");
    if (!definition || !body) return null;
    const lines = body.split(/\n+/);
    const headingIndex = lines.findIndex((line) => definition.headings.some((pattern) => pattern.test(clean(line))));
    if (headingIndex < 0) return null;
    const sectionLines = [];
    for (let index = headingIndex + 1; index < lines.length; index += 1) {
      if (/^\s*\d{1,2}[.．、]/.test(lines[index])) break;
      sectionLines.push(lines[index]);
    }
    const events = sectionLines.map((line) => parseEventLine(line, report.time)).filter(Boolean);
    if (!events.length) return null;
    const amendmentText = [lines[headingIndex], ...sectionLines].join("\n");
    const amendment = amendmentText.match(/改訂追補[：:]?\s*(\d{4}\/\d{1,2}\/\d{1,2})|(\d{4}\/\d{1,2}\/\d{1,2})改訂追補/);
    return {
      schemaVersion: "market-timeline/v1",
      reportId: reportId(report.date, report.time),
      reportDate: report.date,
      reportTime: report.time,
      reportRevision: report.revision ?? null,
      sourceBodyHash: report.bodyHash || null,
      evidenceStatus: amendment ? "AFTER_ISSUANCE_AMENDMENT" : "DERIVED_FROM_SAVED_BODY",
      amendmentDate: amendment ? (amendment[1] || amendment[2]) : null,
      publicationStatus: report.report_status || "UNKNOWN",
      sourceDocumentId: report.sourceDocument?.id || null,
      events
    };
  }

  function verifyTimelineIdentity(timeline, report) {
    if (!timeline || typeof timeline !== "object" || !report) return { valid: false, reason: "タイムラインまたはレポートがありません" };
    const checks = [
      [timeline.reportId, reportId(report.date, report.time)],
      [timeline.reportDate, report.date],
      [timeline.reportTime, report.time],
      [String(timeline.reportRevision ?? ""), String(report.revision ?? "")],
      [timeline.sourceBodyHash, report.bodyHash]
    ];
    if (checks.some(([actual, expected]) => !expected || actual !== expected)) {
      return { valid: false, reason: "日付・時刻・版・本文ハッシュが一致しません" };
    }
    return { valid: true, reason: "" };
  }

  async function verifyArchivedTimeline(timeline, report) {
    const identity = verifyTimelineIdentity(timeline, report);
    if (!identity.valid) return identity;
    if (!report.fullText || !root.crypto?.subtle || typeof root.TextEncoder !== "function") {
      return { valid: false, reason: "本文ハッシュを照合できません" };
    }
    const digest = await root.crypto.subtle.digest("SHA-256", new root.TextEncoder().encode(report.fullText));
    const hash = [...new Uint8Array(digest)].map((byte) => byte.toString(16).padStart(2, "0")).join("");
    if (hash !== timeline.sourceBodyHash) return { valid: false, reason: "保存本文とハッシュが一致しません" };
    if (timeline.sourceDocumentId && report.sourceDocument?.id !== timeline.sourceDocumentId) {
      return { valid: false, reason: "出典文書IDが一致しません" };
    }
    if (timeline.sourceDocumentRevisionId && report.sourceRevisionId !== timeline.sourceDocumentRevisionId) {
      return { valid: false, reason: "出典文書の版が一致しません" };
    }
    return { valid: true, reason: "" };
  }

  root.MarketTimeline = Object.freeze({ SLOT_DEFINITIONS, parseTimelineText, verifyTimelineIdentity, verifyArchivedTimeline, reportId });
  if (typeof module !== "undefined" && module.exports) module.exports = root.MarketTimeline;
})(globalThis);
