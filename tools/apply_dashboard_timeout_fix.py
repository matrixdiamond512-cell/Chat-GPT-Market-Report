from pathlib import Path

GAS_PATH = Path('apps-script/DashboardJsonSync.gs')
JS_PATH = Path('assets/js/top-dashboard.js')


def replace_section(text: str, start_marker: str, end_marker: str, replacement: str) -> str:
    start = text.find(start_marker)
    if start < 0:
        raise RuntimeError(f'start marker not found: {start_marker}')
    end = text.find(end_marker, start)
    if end < 0:
        raise RuntimeError(f'end marker not found: {end_marker}')
    return text[:start] + replacement.rstrip() + '\n\n' + text[end:]


def patch_gas() -> bool:
    text = GAS_PATH.read_text(encoding='utf-8')
    original = text

    first_line_end = text.find('\n')
    if first_line_end >= 0 and text.startswith('// Root-fix version:'):
        text = '// Root-fix version: 2026-08-06 14:06 JST' + text[first_line_end:]

    text = text.replace('  maxReports: 120,', '  maxReports: 1,')

    build_payload = r'''function dashboardBuildPayloadFromReports_(reports) {
  var sourceReports = dashboardNormalizeReports_(reports);
  if (!sourceReports.length) throw new Error('ダッシュボードに使えるマーケットレポートがありません。');

  // dashboard.json は最新レポートだけを保持する。
  // 過去レポート全文は reports.json をブラウザ側で結合して表示するため、
  // ここで120件分を複製・再加工しない。これによりGASの実行時間超過を防ぐ。
  var latestSource = sourceReports[0];
  var priceSource = dashboardFetchPriceSheetSource_(latestSource.date);
  var latest = dashboardPrepareReportForDashboard_(latestSource, priceSource, true);
  var generatedAt = dashboardIsoJst_(new Date());
  var latestKey = latest.date + ' ' + latest.time;
  return {
    schemaVersion: '1.1.0',
    pageId: 'dashboard',
    generatedAt: generatedAt,
    publishedAt: generatedAt,
    dataAsOf: latest.date + 'T' + latest.time + ':00+09:00',
    status: 'ok',
    isStale: dashboardIsStale_(latest.date),
    staleReason: dashboardIsStale_(latest.date) ? '最新レポートの日付が現在日から3日以上離れています。' : '',
    currentReportKey: latestKey,
    sources: dashboardBuildDashboardSources_(latestKey, priceSource),
    errors: dashboardBuildDashboardErrors_(priceSource),
    latestReport: latest,
    reports: [latest]
  };
}'''
    text = replace_section(
        text,
        'function dashboardBuildPayloadFromReports_(reports) {',
        'function dashboardBuildDashboardSources_',
        build_payload,
    )

    text = text.replace(
        "      note: '金・原油・日経225先物・USD/JPY・EUR/USD・BTCUSDの価格、前日比、騰落率は終値一覧を優先して反映します。',",
        "      note: '終値一覧はレポート日と日付が一致する場合だけ反映します。07:00と土曜09:00のみ、4日以内の直近営業日終値を許可します。',",
    )
    text = text.replace(
        "      note: '金・原油・日経225先物・USD/JPY・EUR/USD・BTCUSDの価格、前日比、騰落率は終値一覧を優先して反映します。'",
        "      note: '終値一覧はレポート日と日付が一致する場合だけ反映します。07:00と土曜09:00のみ、4日以内の直近営業日終値を許可します。'",
    )

    price_source = r'''function dashboardFetchPriceSheetSource_(reportDate) {
  var source = {
    id: DASHBOARD_JSON_CONFIG.priceSourceId,
    sheetName: DASHBOARD_JSON_CONFIG.priceSheetName,
    status: 'unavailable',
    asOf: '',
    byDate: {},
    latest: null,
    error: ''
  };

  try {
    if (typeof SpreadsheetApp === 'undefined') return source;
    var spreadsheet = SpreadsheetApp.getActiveSpreadsheet();
    if (!spreadsheet) {
      source.status = 'missing';
      source.error = 'アクティブなスプレッドシートを取得できません。';
      return source;
    }

    var sheet = spreadsheet.getSheetByName(DASHBOARD_JSON_CONFIG.priceSheetName);
    if (!sheet) {
      source.status = 'missing';
      source.error = 'シート「' + DASHBOARD_JSON_CONFIG.priceSheetName + '」が見つかりません。';
      return source;
    }

    var lastRow = sheet.getLastRow();
    var lastColumn = sheet.getLastColumn();
    if (lastRow < 2 || lastColumn < 1) {
      source.status = 'empty';
      source.error = '終値一覧にデータ行がありません。';
      return source;
    }

    // 全シートを一括取得せず、ヘッダー・日付列・必要な行だけ読む。
    var headers = sheet.getRange(1, 1, 1, lastColumn).getDisplayValues()[0] || [];
    var index = dashboardHeaderIndex_(headers);
    if (!Object.prototype.hasOwnProperty.call(index, '日付')) {
      source.status = 'error';
      source.error = '終値一覧に日付列が見つかりません。';
      return source;
    }

    var dateColumn = index['日付'] + 1;
    var dateValues = sheet.getRange(2, dateColumn, lastRow - 1, 1).getDisplayValues();
    var latestDate = '';
    var latestRowNumber = 0;
    var reportRowNumber = 0;

    // 同一日付が複数ある場合は、下側の行を優先する。
    for (var offset = dateValues.length - 1; offset >= 0; offset -= 1) {
      var date = dashboardNormalizeDateKey_(dateValues[offset][0]);
      if (!date) continue;
      var rowNumber = offset + 2;

      if (!reportRowNumber && date === reportDate) reportRowNumber = rowNumber;
      if (!latestDate || date > latestDate) {
        latestDate = date;
        latestRowNumber = rowNumber;
      }
    }

    if (!latestDate || !latestRowNumber) {
      source.status = 'empty';
      source.error = '終値一覧から有効な日付を取得できませんでした。';
      return source;
    }

    if (reportRowNumber) {
      var reportMetricRow = dashboardReadMetricRowAtSheetRow_(
        sheet,
        reportRowNumber,
        lastColumn,
        index,
        reportDate
      );
      if (Object.keys(reportMetricRow.markets).length) source.byDate[reportDate] = reportMetricRow;
    }

    if (latestDate === reportDate && source.byDate[reportDate]) {
      source.latest = source.byDate[reportDate];
    } else {
      var latestMetricRow = dashboardReadMetricRowAtSheetRow_(
        sheet,
        latestRowNumber,
        lastColumn,
        index,
        latestDate
      );
      if (Object.keys(latestMetricRow.markets).length) source.latest = latestMetricRow;
    }

    if (!source.latest && source.byDate[reportDate]) source.latest = source.byDate[reportDate];
    if (!source.latest) {
      source.status = 'empty';
      source.error = '終値一覧の最新日付行から市場価格データを作成できませんでした。';
      return source;
    }

    source.status = 'ok';
    source.asOf = source.latest.date;
    return source;
  } catch (error) {
    source.status = 'error';
    source.error = error.message;
    return source;
  }
}

function dashboardReadMetricRowAtSheetRow_(sheet, rowNumber, lastColumn, index, date) {
  var row = sheet.getRange(rowNumber, 1, 1, lastColumn).getDisplayValues()[0] || [];
  return dashboardBuildPriceMetricRow_(date, row, index);
}'''
    text = replace_section(
        text,
        'function dashboardFetchPriceSheetSource_',
        'function dashboardHeaderIndex_',
        price_source,
    )

    if text != original:
        GAS_PATH.write_text(text, encoding='utf-8')
        return True
    return False


def patch_js() -> bool:
    text = JS_PATH.read_text(encoding='utf-8')
    original = text

    loader = r'''async function loadDashboardReports() {
  const errors = [];
  let dashboardPayload = null;
  let dashboardReports = [];
  let historyReports = [];

  try {
    const response = await fetch(`data/dashboard.json?ts=${Date.now()}`, { cache: "no-store" });
    if (!response.ok) throw new Error(`data/dashboard.json HTTP ${response.status}`);
    dashboardPayload = await response.json();
    dashboardReports = normalizeDashboardReports(dashboardPayload);
  } catch (error) {
    errors.push(error.message);
  }

  // dashboard.json は最新1件だけに軽量化する。
  // 過去分とGoogle Docs由来のfullTextは reports.json から結合する。
  try {
    const response = await fetch(`reports.json?ts=${Date.now()}`, { cache: "no-store" });
    if (!response.ok) throw new Error(`reports.json HTTP ${response.status}`);
    const payload = await response.json();
    historyReports = normalizeDashboardReports(payload);
  } catch (error) {
    errors.push(error.message);
  }

  const mergedByKey = new Map();
  historyReports.forEach((report) => {
    mergedByKey.set(reportKey(report), report);
  });
  dashboardReports.forEach((report) => {
    const key = reportKey(report);
    const history = mergedByKey.get(key) || {};
    mergedByKey.set(key, {
      ...history,
      ...report,
      fullText: report.fullText || history.fullText || ""
    });
  });

  const reportList = [...mergedByKey.values()]
    .filter((report) => /^\d{4}-\d{2}-\d{2}$/.test(report?.date || ""))
    .sort((a, b) => reportKey(b).localeCompare(reportKey(a)));

  if (!reportList.length) {
    throw new Error(`ダッシュボードJSONを取得できませんでした。理由：${errors.join(" / ")}`);
  }

  const embeddedMarketData = dashboardPayload?.marketData || dashboardPayload?.latestReport?.marketData || null;
  const independentMarketData = await loadIndependentMarketData();
  const marketData = newerMarketData(embeddedMarketData, independentMarketData);
  const marketDataReportKey = REPORT_TIMES.includes(marketData?.reportSlot)
    ? `${String(marketData?.generatedAt || "").slice(0, 10)} ${marketData.reportSlot}`
    : "";
  const enrichedReports = reportList.map((report) => {
    const key = `${report.date || ""} ${report.time || ""}`;
    if (marketData && key === marketDataReportKey && !report.marketData) {
      return { ...report, marketData };
    }
    return report;
  });

  return {
    reports: enrichedReports,
    meta: {
      generatedAt: dashboardPayload?.generatedAt || "",
      dataAsOf: dashboardPayload?.dataAsOf || "",
      status: dashboardPayload?.status || (historyReports.length ? "fallback-reports-json" : ""),
      marketData,
      marketDataUpdatedAt: dashboardPayload?.marketDataUpdatedAt || marketData?.generatedAt || ""
    }
  };
}'''
    text = replace_section(
        text,
        'async function loadDashboardReports() {',
        'async function loadIndependentMarketData() {',
        loader,
    )

    if text != original:
        JS_PATH.write_text(text, encoding='utf-8')
        return True
    return False


def main() -> None:
    changed = []
    if patch_gas():
        changed.append(str(GAS_PATH))
    if patch_js():
        changed.append(str(JS_PATH))
    print('Changed:', ', '.join(changed) if changed else 'none')


if __name__ == '__main__':
    main()
