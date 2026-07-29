(() => {
  const asArray = value => Array.isArray(value) ? value : (value ? [value] : []);
  const itemText = value => typeof value === "string"
    ? value
    : (value?.text || value?.summary || value?.title || "");
  const placeholder = value => {
    const text = String(value || "").trim();
    return !text || text === "—" || /^(?:本文参照|旧形式のため原文参照|取得不能|記載なし)$/.test(text) || /^(?:作成日時|基準時刻)/.test(text);
  };

  function firstUseful(...values) {
    for (const value of values) {
      const rows = asArray(value).map(itemText).map(text => String(text || "").trim()).filter(text => !placeholder(text));
      if (rows.length) return rows.join("　");
    }
    return "";
  }

  function populateRequiredCards(report) {
    if (!report) return;
    const conclusion = document.getElementById("dashboardConclusion");
    const risk = document.getElementById("dashboardRisk");

    const conclusionText = firstUseful(
      report.mainScenario,
      report.conclusion,
      report.summary,
      report.outlook,
      report.scenarios?.main,
      report.scenario?.main
    );

    const riskText = firstUseful(
      report.breakConditions,
      report.invalidation,
      report.riskManagement,
      report.risks,
      report.risk,
      report.scenarios?.invalidation,
      report.scenario?.invalidation
    );

    if (conclusion) {
      conclusion.textContent = conclusionText || "取得不能（メインシナリオの構造化データがレポートに登録されていません）";
    }
    if (risk) {
      risk.textContent = riskText || "取得不能（崩れる条件・リスクの構造化データがレポートに登録されていません）";
    }
  }

  function reportScore(report) {
    let score = 0;
    if (report.fullText && report.fullText.length > 500) score += 40;
    if (!placeholder(report.theme)) score += 8;
    if (!placeholder(report.leadingMarket)) score += 6;
    score += Math.min(10, asArray(report.changes).length * 2);
    score += Math.min(10, asArray(report.consistency).length * 2);
    score += Math.min(12, asArray(report.news).length * 2);
    score += Math.min(10, asArray(report.crossAssetFlow).length * 2);
    score += Math.min(10, asArray(report.positioning).length * 2);
    score += Math.min(8, asArray(report.handover).length * 2);
    const markets = asArray(report.markets);
    score += markets.filter(m => !placeholder(m.material) && !placeholder(m.direction)).length * 4;
    return score;
  }

  function isFeatureReady(report) {
    return reportScore(report) >= 55 && asArray(report.markets).filter(m => !placeholder(m.material)).length >= 4;
  }

  async function repairFeaturedReport() {
    try {
      const response = await fetch(`reports.json?quality=${Date.now()}`, { cache: "no-store" });
      if (!response.ok) return;
      let data = await response.json();
      if (!Array.isArray(data)) return;
      if (typeof window.hydrateMarketReport === "function") data = data.map(window.hydrateMarketReport);
      const dated = data
        .filter(r => /^\d{4}-\d{2}-\d{2}$/.test(r.date || ""))
        .sort((a, b) => (`${b.date} ${b.time}`).localeCompare(`${a.date} ${a.time}`));
      const newest = dated[0];
      const featured = dated.find(isFeatureReady);
      const active = featured || newest;
      if (!active) return;

      if (featured && newest && !(featured === newest && isFeatureReady(newest))) {
        if (typeof window.renderDashboard === "function") window.renderDashboard(featured);
        const latestReport = document.getElementById("latestReport");
        const latestTimestamp = document.getElementById("latestTimestamp");
        const heroStatus = document.getElementById("heroStatus");
        if (latestReport && typeof window.reportCard === "function") latestReport.innerHTML = window.reportCard(featured);
        if (latestTimestamp) latestTimestamp.textContent = `内容充実版 ${featured.date.replaceAll("-", "/")} ${featured.time}`;
        if (heroStatus) heroStatus.textContent = `最新の内容充実レポート ${featured.date.replaceAll("-", "/")} ${featured.time}`;

        const notice = document.createElement("p");
        notice.className = "data-quality-notice";
        notice.textContent = `最新時刻の${newest.time}レポートは本文未取り込みのため、内容が揃っている${featured.time}レポートを表示しています。`;
        const section = document.querySelector(".dashboard-section .section-heading");
        if (section && !document.querySelector(".data-quality-notice")) section.insertAdjacentElement("afterend", notice);
      }

      populateRequiredCards(active);
      setTimeout(() => populateRequiredCards(active), 800);
    } catch (error) {
      console.warn("Featured report quality guard failed", error);
      const conclusion = document.getElementById("dashboardConclusion");
      const risk = document.getElementById("dashboardRisk");
      if (conclusion && placeholder(conclusion.textContent)) conclusion.textContent = "取得不能（レポートデータの読み込みに失敗しました）";
      if (risk && placeholder(risk.textContent)) risk.textContent = "取得不能（レポートデータの読み込みに失敗しました）";
    }
  }

  window.populateRequiredDashboardCards = populateRequiredCards;
  window.addEventListener("load", () => setTimeout(repairFeaturedReport, 300));
})();
