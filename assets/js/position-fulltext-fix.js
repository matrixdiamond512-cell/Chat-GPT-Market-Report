/* 2026-08-06 03:27 JST
 * Dashboard-wide full-text fix.
 * Re-render analysis-heavy panels without character truncation.
 */
(function () {
  function fullTextItems(values, limit) {
    return asArray(values)
      .map(textOf)
      .filter(Boolean)
      .map((item) => cleanText(item, Infinity))
      .slice(0, limit);
  }

  renderPositions = function renderPositionsFullText(report) {
    renderList(
      "positionList",
      fullTextItems(report.positioning, 3),
      "理由：需給・ポジション項目がJSONにありません"
    );

    const rows = ["株式", "原油", "ドル", "金", "BTC"];
    const headers = ["", "弱気", "中立", "強気"];
    const cell = (asset, side) => positionBias(report, asset) === side ? "•" : "";

    $("positionMatrix").innerHTML = [
      ...headers.map((header) => `<span>${esc(header)}</span>`),
      ...rows.flatMap((asset) => [
        `<span>${esc(asset)}</span>`,
        ...headers.slice(1).map((side) => `<span class="dot">${cell(asset, side)}</span>`)
      ])
    ].join("");
  };

  function renderFullTextPanels(report) {
    renderProseList(
      "themeList",
      proseItems([report.theme], 5, Infinity),
      "理由：相場テーマがJSONにありません"
    );

    renderProseList(
      "changeList",
      proseItems(report.changes, 4, Infinity),
      "理由：前回からの変化がJSONにありません"
    );

    renderProseBlock(
      "leadingMarket",
      report.leadingMarket,
      "取得不能。理由：主導市場コメントがJSONにありません",
      8,
      Infinity
    );

    renderPositions(report);

    const breakText = breakConditionsFromReport(report, Infinity);
    renderProseBlock(
      "breakConditions",
      breakText,
      "理由：崩れる条件を本文から取得できませんでした",
      8,
      Infinity
    );
    $("breakConditions").classList.toggle("missing", !breakText);

    renderList(
      "handoverList",
      fullTextItems(fallbackHandoverItems(report), 3),
      "理由：引き継ぎ項目がJSONにありません"
    );

    renderProseBlock(
      "conclusionText",
      conclusionFrom(report),
      "理由：結論に必要な項目がJSONにありません",
      8,
      Infinity
    );
  }

  const originalRender = render;
  render = function renderDashboardWithoutTextClipping() {
    originalRender();
    const report = selectedReport || reports[0];
    if (report) renderFullTextPanels(report);
  };
})();
