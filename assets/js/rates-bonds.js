(function () {
  const root = document.querySelector("[data-rates-root]");
  const updatedNode = document.getElementById("pageUpdated");
  const DATA_URL = "data/rates-bonds.json";
  const STATUS_LABELS = {
    confirmed: "確認済み",
    calculated: "計算値",
    estimated: "推定",
    manual: "手入力",
    unavailable: "取得不能",
    stale: "更新失敗",
    planned: "実装予定",
    partial: "一部取得",
    ready: "反映済み"
  };

  if (!root) return;

  const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;"
  })[char]);

  const text = (value, fallback = "取得不能") => {
    if (value === null || value === undefined || value === "" || Number.isNaN(value)) return fallback;
    return String(value);
  };

  const arr = (value) => Array.isArray(value) ? value : [];
  const statusLabel = (status) => STATUS_LABELS[status] || text(status, "取得不能");
  const badge = (status) => `<span class="status-badge ${esc(status || "unavailable")}">${esc(statusLabel(status || "unavailable"))}</span>`;

  const toneClass = (item) => {
    const status = item && typeof item === "object" ? item.status : "";
    if (status === "unavailable" || status === "stale") return "muted";
    const value = text(item && typeof item === "object" ? (item.direction || item.value || item.changeBp) : item, "");
    if (/低下|下落|縮小|弱|売り|悪化|-/.test(value)) return "down";
    if (/上昇|拡大|強|買い|改善|\+/.test(value)) return "up";
    if (/警戒|注意|中/.test(value)) return "warn";
    return "muted";
  };

  const valueWithUnit = (item, valueKey = "value") => {
    if (!item || typeof item !== "object") return esc(text(item));
    const value = item[valueKey];
    if (value === null || value === undefined || value === "" || Number.isNaN(value)) {
      return esc(`取得不能${item.missingReason ? `（${item.missingReason}）` : ""}`);
    }
    return esc(`${value}${item.unit || ""}`);
  };

  const plainValue = (value, fallback = "取得不能") => esc(text(value, fallback));

  function renderHeader(data) {
    const meta = data.meta || {};
    const title = data.pageTitle || "金利・債券市場分析";
    const updated = meta.updatedAt || data.updatedAt || "実データ連携前";
    document.title = `${title}｜WEBマーケットレポート`;
    if (updatedNode) updatedNode.textContent = `最終更新：${updated}`;
    return `
      <div class="page-head">
        <div>
          <h2>${esc(title)}</h2>
          <p>${esc(data.subtitle || "金利の動き、理由、需給、各市場への影響を確認します。")}</p>
        </div>
        <div class="meta-line" aria-label="データ状態">
          <span>基準日：${plainValue(meta.asOfDate, "取得不能")} ${plainValue(meta.asOfTime, "")}</span>
          <span>更新：${plainValue(updated, "実データ連携前")}</span>
          <span>状態：${esc(statusLabel(meta.status || "unavailable"))}</span>
        </div>
      </div>
    `;
  }

  function renderConclusion(data) {
    const summary = data.summary || {};
    const meta = data.meta || {};
    const missing = arr(meta.missingData);
    return `
      <section class="panel conclusion-panel span-12">
        <h2 class="panel-title"><span class="badge-num">1</span>今日の結論</h2>
        <div class="panel-body conclusion-body">
          <div>
            <h3 class="headline">${plainValue(summary.headline, "金利・債券市場データは連携待ちです。")}</h3>
            <p class="lead-text">${plainValue(summary.theme, "実データ連携後に本日の主要テーマを表示します。")}</p>
            <p class="lead-text">${plainValue(summary.conclusion, "確認済みデータが入るまで市場判断は行いません。")}</p>
            <div class="note-box">${plainValue(summary.consistency, "材料と値動きの整合性は未判定です。")}</div>
          </div>
          <div class="status-stack">
            <div class="status-row"><b>データ状態</b><span>${badge(meta.status || "unavailable")}</span></div>
            <div class="status-row"><b>stale</b><span>${meta.isStale ? "はい" : "いいえ"}</span></div>
            <div class="status-row"><b>理由</b><span>${plainValue(meta.staleReason, "取得不能")}</span></div>
            <div class="status-row"><b>未接続</b><span>${missing.length ? esc(missing.slice(0, 4).join("、")) : "なし"}</span></div>
          </div>
        </div>
      </section>
    `;
  }

  function renderCards(data) {
    return `
      <section class="panel span-12">
        <h2 class="panel-title"><span class="badge-num">2</span>4つのサマリーカード</h2>
        <div class="panel-body summary-cards">
          ${arr(data.cards).map((card) => `
            <article class="summary-card">
              <h3>${plainValue(card.label)}</h3>
              <strong class="${toneClass(card)}">${plainValue(card.direction, "取得不能")}</strong>
              ${badge(card.status || "unavailable")}
              <p>${plainValue(card.reason, "理由未設定")}</p>
              <p>基準：${plainValue(card.asOf, "取得不能")}</p>
            </article>
          `).join("")}
        </div>
      </section>
    `;
  }

  function renderRates(data) {
    return `
      <section class="panel span-7">
        <h2 class="panel-title"><span class="badge-num">3</span>主要金利ダッシュボード</h2>
        <div class="panel-body">
          <div class="table-wrap">
            <table class="rates-table">
              <thead>
                <tr>
                  <th>指標</th>
                  <th>現在値</th>
                  <th>前日比bp</th>
                  <th>1週間変化bp</th>
                  <th>方向</th>
                  <th>基準日時</th>
                  <th>状態</th>
                  <th>意味</th>
                </tr>
              </thead>
              <tbody>
                ${arr(data.rates).map((row) => `
                  <tr>
                    <td>${plainValue(row.name)}</td>
                    <td class="num ${toneClass(row)}">${valueWithUnit(row)}</td>
                    <td class="num ${toneClass({ value: row.changeBp, status: row.status })}">${plainValue(row.changeBp)}</td>
                    <td class="num ${toneClass({ value: row.weekChangeBp, status: row.status })}">${plainValue(row.weekChangeBp)}</td>
                    <td>${plainValue(row.direction)}</td>
                    <td>${plainValue(row.asOf)}</td>
                    <td>${badge(row.status || "unavailable")}</td>
                    <td>${plainValue(row.meaning, row.missingReason || "取得不能")}</td>
                  </tr>
                `).join("")}
              </tbody>
            </table>
          </div>
        </div>
      </section>
    `;
  }

  function renderDecomposition(data) {
    const section = data.decomposition || {};
    return `
      <section class="panel span-5">
        <h2 class="panel-title"><span class="badge-num">4</span>米10年債利回りの変化要因</h2>
        <div class="panel-body">
          <p class="plain-note"><b>${plainValue(section.formula, "米10年債利回り = 実質金利 + 期待インフレ率 + タームプレミアム")}</b></p>
          <div class="factor-grid">
            ${arr(section.factors).map((factor) => `
              <article class="factor-card">
                <h3>${plainValue(factor.name)}</h3>
                <strong class="factor-value ${toneClass(factor)}">${valueWithUnit(factor)}</strong>
                ${badge(factor.status || "unavailable")}
                <p>${plainValue(factor.interpretation, "連携後に判定")}</p>
              </article>
            `).join("")}
          </div>
          <div class="note-box">${plainValue(section.point, "変化要因は未判定です。")}</div>
        </div>
      </section>
    `;
  }

  function renderCurve(data) {
    const curve = data.curve || {};
    return `
      <section class="panel span-6">
        <h2 class="panel-title"><span class="badge-num">5</span>イールドカーブ</h2>
        <div class="panel-body">
          <p class="plain-note">${plainValue(curve.summary, "カーブデータは未接続です。")}</p>
          <div class="table-wrap">
            <table class="curve-table">
              <thead>
                <tr><th>スプレッド</th><th>現在値</th><th>前日変化</th><th>1週間変化</th><th>判定</th><th>市場の読み方</th><th>状態</th></tr>
              </thead>
              <tbody>
                ${arr(curve.rows).map((row) => `
                  <tr>
                    <td>${plainValue(row.spread)}</td>
                    <td class="num">${plainValue(row.value)}</td>
                    <td class="num">${plainValue(row.changeBp)}</td>
                    <td class="num">${plainValue(row.weekChangeBp)}</td>
                    <td>${plainValue(row.shape, "未判定")}</td>
                    <td>${plainValue(row.reading, "取得不能")}</td>
                    <td>${badge(row.status || "unavailable")}</td>
                  </tr>
                `).join("")}
              </tbody>
            </table>
          </div>
        </div>
      </section>
    `;
  }

  function renderSupplyDemand(data) {
    const section = data.supplyDemand || {};
    return `
      <section class="panel span-6">
        <h2 class="panel-title"><span class="badge-num">6</span>債券市場の需給状況</h2>
        <div class="panel-body">
          <p class="plain-note">${plainValue(section.summary, "需給データは未接続です。")}</p>
          <div class="supply-grid">
            ${arr(section.items).map((item) => `
              <article class="mini-card">
                <h3>${plainValue(item.name)}</h3>
                <p><b>${valueWithUnit(item)}</b></p>
                ${badge(item.status || "unavailable")}
                <p>${plainValue(item.note, "取得不能")}</p>
                <p>出所：${plainValue(item.source, "未設定")}</p>
              </article>
            `).join("")}
          </div>
        </div>
      </section>
    `;
  }

  function renderPolicy(data) {
    const section = data.policyExpectations || {};
    return `
      <section class="panel span-5">
        <h2 class="panel-title"><span class="badge-num">7</span>中央銀行の政策期待</h2>
        <div class="panel-body">
          <p class="plain-note">${plainValue(section.summary, "政策織り込みデータは未接続です。")}</p>
          <div class="table-wrap">
            <table class="policy-table">
              <thead><tr><th>項目</th><th>現在の織り込み</th><th>前日比</th><th>状態</th><th>出所</th><th>注意点</th></tr></thead>
              <tbody>
                ${arr(section.rows).map((row) => `
                  <tr>
                    <td>${plainValue(row.policy)}</td>
                    <td>${plainValue(row.value)}</td>
                    <td>${plainValue(row.change)}</td>
                    <td>${badge(row.status || "unavailable")}</td>
                    <td>${plainValue(row.source, "未設定")}</td>
                    <td>${plainValue(row.note, "取得不能時は推測しない")}</td>
                  </tr>
                `).join("")}
              </tbody>
            </table>
          </div>
        </div>
      </section>
    `;
  }

  function renderImpact(data) {
    return `
      <section class="panel span-7">
        <h2 class="panel-title"><span class="badge-num">8</span>金利から各市場への波及</h2>
        <div class="panel-body impact-grid">
          ${arr(data.crossAssetImpact).map((item) => `
            <article class="impact-card">
              <h3>${plainValue(item.market)}</h3>
              <p><b>主な金利：</b>${plainValue(item.driver)}</p>
              <ul class="path-list">
                ${arr(item.path).map((step) => `<li>${plainValue(step)}</li>`).join("")}
              </ul>
              ${badge(item.status || "unavailable")}
              <p><b>実際の反応：</b>${plainValue(item.actualStatus, "未判定")}</p>
              <p>${plainValue(item.note, "実データ連携後に判定")}</p>
            </article>
          `).join("")}
        </div>
      </section>
    `;
  }

  function renderLeadingAndScenarios(data) {
    const leading = data.leadingRate || {};
    const scenarios = data.scenarios || {};
    return `
      <section class="panel span-4">
        <h2 class="panel-title"><span class="badge-num">9</span>今日の主導金利</h2>
        <div class="panel-body">
          <article class="leading-card">
            <h3>${plainValue(leading.name)}</h3>
            ${badge(leading.status || "unavailable")}
            <p>${plainValue(leading.reason, "主導金利は未判定です。")}</p>
            <p><b>前回からの変化：</b>${plainValue(leading.changeFromPrevious, "未判定")}</p>
            <p><b>主導が変わる条件：</b>${plainValue(leading.switchCondition, "取得不能")}</p>
          </article>
        </div>
      </section>
      <section class="panel span-8">
        <h2 class="panel-title"><span class="badge-num">10</span>シナリオと崩れる条件</h2>
        <div class="panel-body">
          <div class="scenario-grid">
            <article class="scenario-card">
              <h3>${plainValue((scenarios.main || {}).title, "メインシナリオ")}</h3>
              ${badge((scenarios.main || {}).status || "unavailable")}
              <p>${plainValue((scenarios.main || {}).body, "実データ連携後に表示します。")}</p>
            </article>
            <article class="scenario-card">
              <h3>${plainValue((scenarios.alternative || {}).title, "代替シナリオ")}</h3>
              ${badge((scenarios.alternative || {}).status || "unavailable")}
              <p>${plainValue((scenarios.alternative || {}).body, "実データ連携後に表示します。")}</p>
            </article>
          </div>
          <div class="scenario-grid" style="margin-top:8px">
            <article class="scenario-card">
              <h3>崩れる条件</h3>
              <ul class="watch-list">${arr(scenarios.breakConditions).map((item) => `<li>${plainValue(item)}</li>`).join("")}</ul>
            </article>
            <article class="scenario-card">
              <h3>次の監視ポイント</h3>
              <ul class="watch-list">${arr(scenarios.watchPoints).map((item) => `<li>${plainValue(item)}</li>`).join("")}</ul>
            </article>
          </div>
        </div>
      </section>
    `;
  }

  function renderSources(data) {
    const meta = data.meta || {};
    return `
      <section class="panel span-12">
        <h2 class="panel-title"><span class="badge-num">11</span>データ出所・注意書き</h2>
        <div class="panel-body">
          <div class="table-wrap">
            <table class="source-table">
              <thead><tr><th>情報源</th><th>状態</th><th>注意点</th></tr></thead>
              <tbody>
                ${arr(data.sources).map((source) => `
                  <tr>
                    <td>${plainValue(source.name)}</td>
                    <td>${badge(source.status || "planned")}</td>
                    <td>${plainValue(source.note, "未設定")}</td>
                  </tr>
                `).join("")}
              </tbody>
            </table>
          </div>
          ${arr(data.errors).length ? `<div class="note-box">${arr(data.errors).map((error) => plainValue(error.message, "")).join(" / ")}</div>` : ""}
          <div class="footnotes">
            <span>未接続データ：${meta.missingData && meta.missingData.length ? esc(meta.missingData.join("、")) : "なし"}</span>
            <span>本ページは投資判断の参考情報であり、特定の投資を推奨するものではありません。</span>
          </div>
        </div>
      </section>
    `;
  }

  function render(data) {
    root.innerHTML = `
      ${renderHeader(data)}
      <div class="rb-grid">
        ${renderConclusion(data)}
        ${renderCards(data)}
        ${renderRates(data)}
        ${renderDecomposition(data)}
        ${renderCurve(data)}
        ${renderSupplyDemand(data)}
        ${renderPolicy(data)}
        ${renderImpact(data)}
        ${renderLeadingAndScenarios(data)}
        ${renderSources(data)}
      </div>
    `;
  }

  function renderError(error) {
    const message = error && error.message ? error.message : "理由不明";
    if (updatedNode) updatedNode.textContent = "最終更新：読み込み失敗";
    root.innerHTML = `
      <section class="data-error">
        金利・債券市場データを表示できません。理由：${esc(message)}。data/rates-bonds.jsonを確認してください。
      </section>
    `;
  }

  fetch(`${DATA_URL}?v=${Date.now()}`, { cache: "no-store" })
    .then((response) => {
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return response.json();
    })
    .then(render)
    .catch(renderError);
})();
