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
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  })[char]);
  const arr = (value) => Array.isArray(value) ? value : [];
  const text = (value, fallback = "—") => {
    if (value === null || value === undefined || value === "" || Number.isNaN(value)) return fallback;
    return String(value);
  };
  const plainValue = (value, fallback = "—") => esc(text(value, fallback));
  const statusLabel = (status) => STATUS_LABELS[status] || text(status, "取得不能");
  const badge = (status) => `<span class="status-badge ${esc(status || "unavailable")}">${esc(statusLabel(status || "unavailable"))}</span>`;
  const available = (item) => item && item.status !== "unavailable" && item.status !== "stale";
  const hasValue = (item, key = "value") => item && item[key] !== null && item[key] !== undefined && item[key] !== "";

  const toneClass = (item) => {
    if (!item || item.status === "unavailable" || item.status === "stale") return "muted";
    const value = text(item.direction ?? item.changeBp ?? item.value, "");
    if (/低下|下落|縮小|弱|売り|悪化/.test(value)) return "down";
    if (/上昇|拡大|強|買い|改善/.test(value)) return "up";
    if (/警戒|注意|逆イールド/.test(value)) return "warn";
    if (typeof item.changeBp === "number") return item.changeBp > 0 ? "up" : item.changeBp < 0 ? "down" : "muted";
    return "muted";
  };

  const valueWithUnit = (item, key = "value", fallback = "—") => {
    if (!item || !hasValue(item, key)) return esc(fallback);
    return esc(`${item[key]}${item.unit || ""}`);
  };

  const signedBp = (value) => {
    if (value === null || value === undefined || value === "") return "—";
    const num = Number(value);
    if (!Number.isFinite(num)) return esc(value);
    return `${num > 0 ? "+" : ""}${num.toFixed(1)}`;
  };

  function renderHeader(data) {
    const meta = data.meta || {};
    const title = data.pageTitle || "金利・債券市場分析";
    const updated = meta.updatedAt || data.generatedAt || "—";
    document.title = `${title}｜WEBマーケットレポート`;
    if (updatedNode) updatedNode.textContent = `最終更新：${updated}`;
    return `
      <div class="page-head">
        <div>
          <h2>${esc(title)}</h2>
          <p>${esc(data.subtitle || "米・日・欧の金利と債券市場を一画面で確認")}</p>
        </div>
        <div class="meta-line" aria-label="データ状態">
          <span>基準日：${plainValue(meta.asOfDate)} ${plainValue(meta.asOfTime, "")}</span>
          <span>更新：${plainValue(updated)}</span>
          <span>データ状態：${esc(statusLabel(meta.status || "unavailable"))}</span>
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
        <h2 class="panel-title"><span class="badge-num">1</span>今日の金利・債券市場の結論</h2>
        <div class="panel-body conclusion-body">
          <div>
            <h3 class="headline">${plainValue(summary.headline, "主要金利を取得中")}</h3>
            <p class="lead-text">${plainValue(summary.theme, "取得済みデータから方向を判定します。")}</p>
            <p class="lead-text">${plainValue(summary.conclusion, "未取得値は推測しません。")}</p>
            <div class="note-box"><b>材料と値動きの整合性：</b>${plainValue(summary.consistency, "判定待ち")}</div>
          </div>
          <div class="status-stack">
            <div class="status-row"><b>データ状態</b><span>${badge(meta.status || "unavailable")}</span></div>
            <div class="status-row"><b>基準日</b><span>${plainValue(meta.asOfDate)}</span></div>
            <div class="status-row"><b>取得方式</b><span>${plainValue(meta.sourceStatus, "自動取得")}</span></div>
            <div class="status-row"><b>未取得</b><span>${missing.length ? esc(missing.slice(0, 4).join("、")) + (missing.length > 4 ? ` ほか${missing.length - 4}件` : "") : "なし"}</span></div>
          </div>
        </div>
      </section>
    `;
  }

  function renderCards(data) {
    const cards = arr(data.cards).filter(available);
    if (!cards.length) return "";
    return `
      <section class="panel span-12">
        <h2 class="panel-title"><span class="badge-num">2</span>市場の要点</h2>
        <div class="panel-body summary-cards">
          ${cards.map((card) => `
            <article class="summary-card">
              <h3>${plainValue(card.label)}</h3>
              <strong class="${toneClass(card)}">${plainValue(card.direction)}</strong>
              <p>${plainValue(card.reason)}</p>
              <p class="small-meta">基準日：${plainValue(card.asOf)} ｜ 最終取得：${plainValue(card.fetchedAt || card.updatedAt || data.meta?.updatedAt || data.generatedAt)} ｜ ${plainValue(card.frequency, "日次")} ｜ ${esc(statusLabel(card.status || "confirmed"))}</p>
            </article>
          `).join("")}
        </div>
      </section>
    `;
  }

  function renderRates(data) {
    const rows = arr(data.rates).filter((row) => available(row) && hasValue(row));
    if (!rows.length) return "";
    const groupOf = (name) => name.startsWith("米") ? "米国" : name.startsWith("日本") ? "日本" : name.startsWith("ドイツ") ? "欧州" : "その他";
    return `
      <section class="panel span-12">
        <h2 class="panel-title"><span class="badge-num">3</span>主要金利ダッシュボード</h2>
        <div class="panel-body">
          <div class="table-wrap">
            <table class="rates-table">
              <thead><tr><th>地域</th><th>指標</th><th>現在値</th><th>前日比</th><th>1週間</th><th>方向</th><th>基準日</th><th>市場での意味</th></tr></thead>
              <tbody>
                ${rows.map((row) => `
                  <tr>
                    <td class="region-cell">${groupOf(row.name)}</td>
                    <td>${plainValue(row.name)}</td>
                    <td class="num ${toneClass(row)}">${valueWithUnit(row)}</td>
                    <td class="num ${toneClass({ changeBp: row.changeBp, status: row.status })}">${signedBp(row.changeBp)} bp</td>
                    <td class="num">${signedBp(row.weekChangeBp)} bp</td>
                    <td class="${toneClass(row)}">${plainValue(row.direction)}</td>
                    <td>${plainValue(row.asOf)}</td>
                    <td>${plainValue(row.meaning)}</td>
                  </tr>
                `).join("")}
              </tbody>
            </table>
          </div>
        </div>
      </section>
    `;
  }

  function curveScale(points) {
    const valid = points.filter((p) => available(p) && hasValue(p));
    if (!valid.length) return "";
    const values = valid.map((p) => Number(p.value)).filter(Number.isFinite);
    if (!values.length) return "";
    const min = Math.min(...values);
    const max = Math.max(...values);
    const range = Math.max(max - min, 0.1);
    return `
      <div class="curve-strip">
        ${valid.map((p) => {
          const pos = ((Number(p.value) - min) / range) * 74 + 8;
          return `<div class="curve-point" style="--curve-pos:${pos}%"><span class="curve-dot"></span><b>${plainValue(p.tenor)}</b><strong>${Number(p.value).toFixed(3)}%</strong></div>`;
        }).join("")}
      </div>
    `;
  }

  function renderCurve(data) {
    const curve = data.curve || {};
    const rows = arr(curve.rows).filter((row) => available(row) && hasValue(row));
    const usCurve = arr(curve.usCurve).filter((row) => available(row) && hasValue(row));
    const jpCurve = arr(curve.jpCurve).filter((row) => available(row) && hasValue(row));
    if (!rows.length && !usCurve.length && !jpCurve.length) return "";
    return `
      <section class="panel span-7">
        <h2 class="panel-title"><span class="badge-num">4</span>イールドカーブ</h2>
        <div class="panel-body">
          <p class="plain-note curve-summary">${plainValue(curve.summary)}</p>
          <div class="curve-visual-grid">
            ${usCurve.length ? `<article class="curve-panel"><h3>米国債</h3>${curveScale(usCurve)}</article>` : ""}
            ${jpCurve.length ? `<article class="curve-panel"><h3>日本国債</h3>${curveScale(jpCurve)}</article>` : ""}
          </div>
          ${rows.length ? `<div class="table-wrap"><table class="curve-table"><thead><tr><th>スプレッド</th><th>現在値</th><th>前日変化</th><th>1週間変化</th><th>形状</th><th>変化の読み方</th></tr></thead><tbody>${rows.map((row) => `<tr><td>${plainValue(row.spread)}</td><td class="num">${plainValue(row.value)} bp</td><td class="num">${signedBp(row.changeBp)} bp</td><td class="num">${signedBp(row.weekChangeBp)} bp</td><td class="${/逆イールド/.test(row.shape || "") ? "warn" : ""}">${plainValue(row.shape)}</td><td>${plainValue(row.reading)}</td></tr>`).join("")}</tbody></table></div>` : ""}
        </div>
      </section>
    `;
  }

  function renderDecomposition(data) {
    const section = data.decomposition || {};
    const factors = arr(section.factors).filter(available);
    if (!factors.length) return "";
    return `
      <section class="panel span-5">
        <h2 class="panel-title"><span class="badge-num">5</span>米10年金利の変化要因</h2>
        <div class="panel-body">
          <p class="plain-note"><b>${plainValue(section.formula)}</b></p>
          <div class="factor-grid">
            ${factors.map((factor) => `
              <article class="factor-card">
                <h3>${plainValue(factor.name)}</h3>
                <strong class="factor-value ${toneClass(factor)}">${valueWithUnit(factor)}</strong>
                <p>${plainValue(factor.interpretation)}</p><p class="small-meta">基準日：${plainValue(factor.asOf)} ｜ 最終取得：${plainValue(factor.fetchedAt || data.meta?.updatedAt || data.generatedAt)} ｜ ${plainValue(factor.frequency, "日次")}</p>
              </article>
            `).join("")}
          </div>
          <div class="note-box">${plainValue(section.point)}</div>
        </div>
      </section>
    `;
  }

  function renderSupplyDemand(data) {
    const section = data.supplyDemand || {};
    const items = arr(section.items).filter((item) => available(item) && hasValue(item));
    if (!items.length) return "";
    return `
      <section class="panel span-6">
        <h2 class="panel-title"><span class="badge-num">6</span>債券需給・米国債入札</h2>
        <div class="panel-body">
          <p class="plain-note">${plainValue(section.summary)}</p>
          <div class="supply-grid">
            ${items.map((item) => `<article class="mini-card"><h3>${plainValue(item.name)}</h3><p class="metric-line"><b>${valueWithUnit(item)}</b></p><p>${plainValue(item.note)}</p><p class="small-meta">基準日：${plainValue(item.asOf)} ｜ 最終取得：${plainValue(item.fetchedAt || data.meta?.updatedAt || data.generatedAt)} ｜ ${plainValue(item.frequency, "イベント時")}</p><p class="small-meta">出所：${plainValue(item.source)}</p></article>`).join("")}
          </div>
        </div>
      </section>
    `;
  }

  function renderPolicy(data) {
    const section = data.policyExpectations || {};
    const rows = arr(section.rows).filter(available);
    if (!rows.length) return "";
    return `
      <section class="panel span-6">
        <h2 class="panel-title"><span class="badge-num">7</span>政策金利・短期金利期待</h2>
        <div class="panel-body">
          <p class="plain-note">${plainValue(section.summary)}</p>
          <div class="table-wrap"><table class="policy-table"><thead><tr><th>項目</th><th>現在</th><th>変化</th><th>出所</th><th>読み方</th></tr></thead><tbody>${rows.map((row) => `<tr><td>${plainValue(row.policy)}</td><td>${plainValue(row.value)}</td><td>${plainValue(row.change)}</td><td>${plainValue(row.source)}</td><td>${plainValue(row.note)}</td></tr>`).join("")}</tbody></table></div>
        </div>
      </section>
    `;
  }

  function renderImpact(data) {
    const items = arr(data.crossAssetImpact).filter(available);
    if (!items.length) return "";
    return `
      <section class="panel span-12">
        <h2 class="panel-title"><span class="badge-num">8</span>金利から各市場への波及と実際の反応</h2>
        <div class="panel-body impact-grid impact-five">
          ${items.map((item) => `<article class="impact-card"><h3>${plainValue(item.market)}</h3><p><b>主な金利：</b>${plainValue(item.driver)}</p><ul class="path-list">${arr(item.path).map((step) => `<li>${plainValue(step)}</li>`).join("")}</ul><p class="actual-reaction"><b>実際：</b>${plainValue(item.actualStatus)}</p><p>${plainValue(item.note)}</p></article>`).join("")}
        </div>
      </section>
    `;
  }

  function renderLeadingAndScenarios(data) {
    const leading = data.leadingRate || {};
    const scenarios = data.scenarios || {};
    const main = scenarios.main || {};
    const alt = scenarios.alternative || {};
    return `
      <section class="panel span-4">
        <h2 class="panel-title"><span class="badge-num">9</span>今日の主導金利</h2>
        <div class="panel-body"><article class="leading-card"><h3>${plainValue(leading.name)}</h3><p>${plainValue(leading.reason)}</p><p><b>前日から：</b>${plainValue(leading.changeFromPrevious)}</p><p><b>主導が変わる条件：</b>${plainValue(leading.switchCondition)}</p></article></div>
      </section>
      <section class="panel span-8">
        <h2 class="panel-title"><span class="badge-num">10</span>シナリオと見方を変える条件</h2>
        <div class="panel-body">
          <div class="scenario-grid"><article class="scenario-card"><h3>${plainValue(main.title, "メインシナリオ")}</h3><p>${plainValue(main.body)}</p></article><article class="scenario-card"><h3>${plainValue(alt.title, "代替シナリオ")}</h3><p>${plainValue(alt.body)}</p></article></div>
          <div class="scenario-grid scenario-lists"><article class="scenario-card"><h3>シナリオが崩れる条件</h3><ul class="watch-list">${arr(scenarios.breakConditions).map((item) => `<li>${plainValue(item)}</li>`).join("")}</ul></article><article class="scenario-card"><h3>次に見るポイント</h3><ul class="watch-list">${arr(scenarios.watchPoints).map((item) => `<li>${plainValue(item)}</li>`).join("")}</ul></article></div>
        </div>
      </section>
    `;
  }

  function renderSources(data) {
    const sources = arr(data.sources);
    const errors = arr(data.errors);
    return `
      <section class="panel span-12 source-panel">
        <h2 class="panel-title"><span class="badge-num">11</span>データ出所・更新ルール</h2>
        <div class="panel-body">
          <div class="source-chips">${sources.map((source) => `<span class="source-chip ${esc(source.status || "unavailable")}"><b>${plainValue(source.name)}</b><small>${plainValue(source.note)}</small></span>`).join("")}</div>
          ${errors.length ? `<details class="data-details"><summary>今回取得できなかった補助データ</summary><ul>${errors.map((error) => `<li>${plainValue(error.message)}</li>`).join("")}</ul></details>` : ""}
          <div class="footnotes"><span>未取得項目は推測値で埋めません。取得済みの公式・検証済みデータだけで分析します。</span><span>投資判断の参考情報であり、特定の投資を推奨するものではありません。</span></div>
        </div>
      </section>
    `;
  }

  function render(data) {
    root.innerHTML = `${renderHeader(data)}<div class="rb-grid">${renderConclusion(data)}${renderCards(data)}${renderRates(data)}${renderCurve(data)}${renderDecomposition(data)}${renderSupplyDemand(data)}${renderPolicy(data)}${renderImpact(data)}${renderLeadingAndScenarios(data)}${renderSources(data)}</div>`;
  }

  function renderError(error) {
    const message = error && error.message ? error.message : "理由不明";
    if (updatedNode) updatedNode.textContent = "最終更新：読み込み失敗";
    root.innerHTML = `<section class="data-error"><b>金利・債券市場データを表示できません。</b><br>理由：${esc(message)}<br>更新処理が次回成功するまで、古い値や推測値では埋めません。</section>`;
  }

  fetch(`${DATA_URL}?v=${Date.now()}`, { cache: "no-store" })
    .then((response) => {
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return response.json();
    })
    .then(render)
    .catch(renderError);
})();
