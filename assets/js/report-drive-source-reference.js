/* Latest saved Google Drive selection is a reference, never a formal publication gate. */
(() => {
  "use strict";
  let selected = new Map();
  const path = "data/drive-source-selection.json";
  const allowed = /^https:\/\/(?:docs\.google\.com\/document\/d\/|drive\.google\.com\/file\/d\/)[-\w]+\//;
  function linkFor(entry, label) {
    if (!allowed.test(String(entry.driveUrl || ""))) return null;
    const a = document.createElement("a");
    a.href = entry.driveUrl;
    a.target = "_blank";
    a.rel = "noopener noreferrer";
    a.textContent = label;
    return a;
  }
  function paragraph(container, content, link) {
    const p = document.createElement("p");
    p.style.margin = "4px 0";
    p.append(document.createTextNode(content));
    if (link) { p.append(" "); p.append(link); }
    container.append(p);
  }
  function update() {
    const report = window.MarketReportLastRendered;
    const app = document.getElementById("app");
    if (!report || !app) return;
    app.querySelector(".drive-source-reference")?.remove();
    const key = String(report.date || "") + "_" + String(report.time || "").replace(":", "-");
    const entries = selected.get(key);
    if (!entries?.length) return;
    const panel = document.createElement("aside");
    panel.className = "drive-source-reference";
    panel.setAttribute("aria-label", "Google Driveの保存版");
    Object.assign(panel.style, {margin:"12px 0",padding:"10px 14px",border:"1px solid #cbd5e1",borderRadius:"6px",fontSize:"0.9rem",lineHeight:"1.6"});
    const heading = document.createElement("strong");
    heading.textContent = "Google Drive保存版（同名ファイル中、保存日時が最新）";
    panel.append(heading);
    entries.forEach(entry => {
      if (entry.kind === "document") {
        const full = entry.bodyCheck === "STRUCTURE_CHECK_PASSED";
        const note = full
          ? "本文の形は確認済み。公開済み本文の上書きは、発行証拠・版管理の照合後です。"
          : "選ばれた保存版は空または本文不足です。公開中の本文は保護しています。";
        paragraph(panel, note, linkFor(entry,"選定されたGoogleドキュメントを開く"));
      } else if (entry.kind === "image") {
        paragraph(panel,"図解の保存日時は照合済み。公開用の画像ハッシュとmanifestは未検証です。",linkFor(entry,"選定された図解PNGを開く"));
      }
    });
    const footer = document.createElement("small");
    footer.textContent = "保存版の選定とGitHub・ポータルの正式発行認定は別です。";
    panel.append(footer);
    const head = app.querySelector(".report-head");
    if (head) head.insertAdjacentElement("afterend",panel);
    else app.prepend(panel);
  }
  window.addEventListener("market-report-rendered", update);
  fetch(path+"?ts="+Date.now(),{cache:"no-store"})
    .then(r => { if (!r.ok) throw new Error("Drive source inventory fetch failed"); return r.json(); })
    .then(data => {
      if (data.schemaVersion !== 1 || !Array.isArray(data.items)) return;
      selected = new Map();
      for (const entry of data.items) {
        if (!/^20\d{2}-\d{2}-\d{2}_\d{2}-\d{2}$/.test(String(entry.slotKey||""))) continue;
        if (!selected.has(entry.slotKey)) selected.set(entry.slotKey,[]);
        selected.get(entry.slotKey).push(entry);
      }
      update();
    })
    .catch(err => console.warn("[saved Drive source references]",err.message));
})();
