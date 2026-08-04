(function () {
  "use strict";

  var REFRESH_TEXT = "\u66f4\u65b0";
  var REFRESH_LABEL = "\u30da\u30fc\u30b8\u3092\u66f4\u65b0";

  function createRefreshButton() {
    var button = document.createElement("button");
    button.type = "button";
    button.className = "site-refresh-button";
    button.textContent = REFRESH_TEXT;
    button.setAttribute("aria-label", REFRESH_LABEL);
    return button;
  }

  function prepareRefreshButton(button) {
    if (!button || button.dataset.siteRefreshReady === "1") return;
    button.dataset.siteRefreshReady = "1";
    button.type = "button";
    button.classList.add("site-refresh-button");
    button.textContent = REFRESH_TEXT;
    button.setAttribute("aria-label", REFRESH_LABEL);
    button.addEventListener("click", function () {
      window.location.reload();
    });
  }

  function findHeaderInner(header) {
    return (
      header.querySelector(".header-inner") ||
      header.querySelector(".mt-top-inner") ||
      header.querySelector(".top-inner") ||
      header.querySelector(".head-inner") ||
      header.querySelector(".rb-top-inner") ||
      header.querySelector(".sd-head-row") ||
      header
    );
  }

  function ensureRefreshButton() {
    var buttons = Array.prototype.slice.call(
      document.querySelectorAll(".update-btn, .site-refresh-button")
    );

    if (buttons.length === 0) {
      var header = document.querySelector("header");
      if (header) {
        var inner = findHeaderInner(header);
        var actions = document.createElement("div");
        actions.className = "site-page-actions";
        actions.appendChild(createRefreshButton());
        inner.appendChild(actions);
        buttons = Array.prototype.slice.call(
          document.querySelectorAll(".update-btn, .site-refresh-button")
        );
      }
    }

    buttons.forEach(prepareRefreshButton);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", ensureRefreshButton);
  } else {
    ensureRefreshButton();
  }
})();
