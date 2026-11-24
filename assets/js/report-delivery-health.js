/* Scheduled publication freshness; independent of selected historical report. */
(function (root) {
  "use strict";
  function assess(dashboard, schedule, now) {
    now = now || new Date();
    if (schedule.timezone !== "Asia/Tokyo" || !Number.isFinite(now.getTime())) throw new Error("Invalid schedule/time");
    const jst = new Date(now.getTime() + 9 * 3600000);
    let expected;
    for (let back = 0; back < 8 && !expected; back++) {
      const day = new Date(Date.UTC(jst.getUTCFullYear(), jst.getUTCMonth(), jst.getUTCDate() - back));
      const weekday = day.getUTCDay();
      const key = weekday === 0 ? "sunday" : weekday === 6 ? "saturday" : "weekday";
      const date = day.toISOString().slice(0, 10);
      for (const slot of [...schedule[key].publicationSlots].sort().reverse()) {
        const candidate = new Date(date + "T" + slot + ":00+09:00");
        if (candidate <= now) { expected = { date, slot, timestamp: candidate.getTime() }; break; }
      }
    }
    if (!expected) throw new Error("No scheduled publication");
    const published = Date.parse(dashboard.dataAsOf || "");
    const behind = !Number.isFinite(published) || published !== expected.timestamp;
    return { behind, expected: expected.date + " " + expected.slot, published: dashboard.dataAsOf || "未確認" };
  }
  if (typeof module === "object" && module.exports) module.exports = { assess };
  if (!root.document) return;
  const document = root.document;
  let banner;
  function show(message) {
    if (!banner) {
      banner = document.createElement("aside");
      banner.id = "report-delivery-health";
      banner.setAttribute("role", "status");
      const main = document.querySelector("main");
      (main || document.body).prepend(banner);
    }
    banner.textContent = message;
    banner.hidden = !message;
  }
  async function update() {
    try {
      const values = await Promise.all(["data/dashboard.json", "config/report_schedule.json"].map(async path => {
        const response = await root.fetch(path, { cache: "no-store" });
        if (!response.ok) throw new Error("Delivery status unavailable");
        return response.json();
      }));
      const health = assess(values[0], values[1]);
      show(health.behind ? `正式レポートの更新が遅れています。予定枠：${health.expected} JST ／ 公開済み：${health.published}。保存記録・過去レポートは定時配信成功を示しません。` : "");
    } catch (_) {
      show("正式レポートの配信状態を確認できません。最新枠の公開は未確認です。");
    }
  }
  update();
  root.setInterval(update, 60000);
})(typeof window === "undefined" ? globalThis : window);
