(() => {
  "use strict";

  const INTERNAL_DETAIL_PATTERNS = [
    /週間カレンダーをJST変換/i,
    /WEBマーケットレポート独自の重要度と市場対応を付与/i,
    /元JSONは公開保存しません/i
  ];

  function isInternalDetail(text) {
    return INTERNAL_DETAIL_PATTERNS.some((pattern) => pattern.test(text));
  }

  function cleanEventDetails() {
    document.querySelectorAll("#eventRows .event-detail").forEach((element) => {
      const parts = String(element.textContent || "")
        .split(/\s*\/\s*/)
        .map((part) => part.trim())
        .filter(Boolean)
        .filter((part) => !isInternalDetail(part));

      if (!parts.length) {
        element.remove();
        return;
      }
      element.textContent = parts.join(" / ");
    });
  }

  function start() {
    const target = document.getElementById("eventRows");
    if (!target) return;
    cleanEventDetails();
    new MutationObserver(cleanEventDetails).observe(target, {
      childList: true,
      subtree: true,
      characterData: true
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start, { once: true });
  } else {
    start();
  }
})();
