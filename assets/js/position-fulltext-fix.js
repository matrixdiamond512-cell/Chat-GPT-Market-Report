/* 2026-08-06 hotfix: render positioning entries without character truncation. */
(function () {
  renderPositions = function renderPositionsFullText(report) {
    renderList(
      "positionList",
      topList(report.positioning, 3, Infinity),
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
})();
