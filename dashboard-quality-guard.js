(() => {
  const asArray = value => Array.isArray(value) ? value : (value ? [value] : []);
  const placeholder = value => {
    const text = String(value || "").trim();
    return !text || /^(?:本文参照|旧形式のため原文参照|取得不能|記載なし)$/.test(text) || /^(?:作成日時|基準時刻)/.test(text);
  };

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
      if (!featured || !newest || featured === newest && isFeatureReady(newest)) return;

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
    } catch (error) {
      console.warn("Featured report quality guard failed", error);
    }
  }

  window.addEventListener("load", () => setTimeout(repairFeaturedReport, 300));
})();
