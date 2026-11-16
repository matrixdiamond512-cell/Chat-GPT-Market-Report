(function () {
  "use strict";

  const ARCHIVE_BASE = "data/rates-bonds-archive/";
  const INDEX_URL = `${ARCHIVE_BASE}index.json`;
  const params = new URLSearchParams(window.location.search);
  const requestedDate = String(params.get("date") || "").trim();
  const isIsoDate = (value) => /^\d{4}-\d{2}-\d{2}$/.test(String(value || ""));
  const nativeFetch = window.fetch.bind(window);

  // rates-bonds.js は data/rates-bonds.json を読む設計のまま維持する。
  // ?date=YYYY-MM-DD が指定されたときだけ、同じ描画処理へ日次アーカイブを渡す。
  if (isIsoDate(requestedDate)) {
    window.fetch = function (input, init) {
      const url = typeof input === "string" ? input : (input && input.url) || "";
      if (/^data\/rates-bonds\.json(?:[?#]|$)/.test(url)) {
        const query = url.includes("?") ? url.slice(url.indexOf("?")) : `?v=${Date.now()}`;
        return nativeFetch(`${ARCHIVE_BASE}${requestedDate}.json${query}`, init);
      }
      return nativeFetch(input, init);
    };
  }

  function slashDate(value) {
    return isIsoDate(value) ? value.replaceAll("-", "/") : "取得不能";
  }

  function reportList(payload) {
    const rows = Array.isArray(payload && payload.reports) ? payload.reports : [];
    return rows
      .filter((row) => row && isIsoDate(row.date) && row.file)
      .sort((a, b) => a.date.localeCompare(b.date));
  }

  function nearestOnOrBefore(rows, value) {
    if (!rows.length) return null;
    const before = rows.filter((row) => row.date <= value);
    return before.length ? before[before.length - 1] : rows[0];
  }

  function goToDate(date, latestDate) {
    const base = "rates-bonds.html";
    if (!date || date === latestDate) {
      window.location.href = base;
      return;
    }
    window.location.href = `${base}?date=${encodeURIComponent(date)}`;
  }

  function setBusy(root, busy) {
    if (!root) return;
    root.setAttribute("aria-busy", busy ? "true" : "false");
  }

  function initCalendar() {
    const shell = document.querySelector("[data-rates-history]");
    const dateInput = document.getElementById("rbDateInput");
    const prevButton = document.getElementById("rbPrevDate");
    const nextButton = document.getElementById("rbNextDate");
    const status = document.getElementById("rbHistoryStatus");
    if (!shell || !dateInput || !prevButton || !nextButton || !status) return;

    setBusy(shell, true);
    nativeFetch(`${INDEX_URL}?v=${Date.now()}`, { cache: "no-store" })
      .then((response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return response.json();
      })
      .then((payload) => {
        const rows = reportList(payload);
        if (!rows.length) throw new Error("履歴がまだありません");

        const latest = rows[rows.length - 1];
        const latestDate = latest.date;
        let selected = requestedDate && isIsoDate(requestedDate)
          ? rows.find((row) => row.date === requestedDate)
          : latest;

        if (!selected && isIsoDate(requestedDate)) {
          selected = nearestOnOrBefore(rows, requestedDate);
          if (selected) {
            window.location.replace(selected.date === latestDate
              ? "rates-bonds.html"
              : `rates-bonds.html?date=${encodeURIComponent(selected.date)}`);
            return;
          }
        }
        selected = selected || latest;

        const index = rows.findIndex((row) => row.date === selected.date);
        dateInput.min = rows[0].date;
        dateInput.max = latestDate;
        dateInput.value = selected.date;
        prevButton.disabled = index <= 0;
        nextButton.disabled = index < 0 || index >= rows.length - 1;

        const isLatest = selected.date === latestDate && !requestedDate;
        const usDate = selected.usDataDate || selected.asOfDate;
        const jpDate = selected.japanDataDate || selected.asOfDate;
        status.dataset.mode = isLatest ? "latest" : "historical";
        status.textContent = `${isLatest ? "最新表示" : "過去表示"}｜米国市場データ ${slashDate(usDate)}｜日本市場データ ${slashDate(jpDate)}`;

        prevButton.addEventListener("click", () => {
          if (index > 0) goToDate(rows[index - 1].date, latestDate);
        });
        nextButton.addEventListener("click", () => {
          if (index >= 0 && index < rows.length - 1) goToDate(rows[index + 1].date, latestDate);
        });
        dateInput.addEventListener("change", () => {
          const value = dateInput.value;
          if (!isIsoDate(value)) return;
          const exact = rows.find((row) => row.date === value);
          const target = exact || nearestOnOrBefore(rows, value);
          if (!target) return;
          if (!exact) {
            status.textContent = `${slashDate(value)} の保存レポートはありません。直前の保存日 ${slashDate(target.date)} を表示します。`;
          }
          goToDate(target.date, latestDate);
        });
      })
      .catch((error) => {
        dateInput.value = isIsoDate(requestedDate) ? requestedDate : "";
        prevButton.disabled = true;
        nextButton.disabled = true;
        status.dataset.mode = "error";
        status.textContent = `履歴一覧を読み込めませんでした（${error.message || "理由不明"}）。最新データ表示は継続します。`;
      })
      .finally(() => setBusy(shell, false));
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initCalendar, { once: true });
  } else {
    initCalendar();
  }
})();
