(() => {
  "use strict";

  const CRYPTO_ID = "sentiment.crypto_fear_greed";
  let applying = false;

  function removeCryptoElements() {
    if (applying) return;
    applying = true;
    try {
      document.querySelectorAll("#temperatureMiniCards article, #environmentSummary article").forEach((node) => {
        const text = String(node.textContent || "").replace(/\s+/g, " ").trim();
        if (/Crypto\s+Fear\s*&\s*Greed|暗号資産心理/.test(text)) {
          node.remove();
        }
      });

      document.querySelectorAll("#environmentSummary li").forEach((node) => {
        const text = String(node.textContent || "").replace(/\s+/g, " ").trim();
        if (/Crypto\s+Fear\s*&\s*Greed|暗号資産心理/.test(text)) {
          node.remove();
        }
      });
    } finally {
      applying = false;
    }
  }

  if (typeof environmentVerdict === "function") {
    const originalEnvironmentVerdict = environmentVerdict;
    environmentVerdict = function cryptoFreeEnvironmentVerdict(metrics, report) {
      const filtered = Array.isArray(metrics)
        ? metrics.filter((item) => item?.definition?.id !== CRYPTO_ID)
        : metrics;
      const verdict = originalEnvironmentVerdict(filtered, report);
      if (verdict && typeof verdict.reason === "string") {
        verdict.reason = verdict.reason.replace("必須データ4項目中", "必須データ3項目中");
      }
      return verdict;
    };
  }

  if (typeof renderTemperatureMini === "function") {
    const originalRenderTemperatureMini = renderTemperatureMini;
    renderTemperatureMini = function cryptoFreeRenderTemperatureMini(report) {
      originalRenderTemperatureMini(report);
      removeCryptoElements();
    };
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", removeCryptoElements, { once: true });
  } else {
    removeCryptoElements();
  }

  const observer = new MutationObserver(removeCryptoElements);
  observer.observe(document.documentElement, { childList: true, subtree: true });
})();
