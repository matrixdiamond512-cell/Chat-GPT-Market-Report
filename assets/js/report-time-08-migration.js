(() => {
  "use strict";
  try {
    if (typeof REPORT_TIMES !== "undefined" && Array.isArray(REPORT_TIMES)) {
      REPORT_TIMES.splice(0, REPORT_TIMES.length, "08:00", "12:00", "16:00", "21:00");
    }
  } catch (error) {
    console.warn("08:00 report-time migration failed", error);
  }
})();
