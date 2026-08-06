from __future__ import annotations

import re
from pathlib import Path

TARGET = Path("apps-script/DashboardJsonSync.gs")


def replace_once(source: str, pattern: str, replacement: str, label: str, *, flags: int = 0) -> str:
    updated, count = re.subn(pattern, replacement, source, count=1, flags=flags)
    if count != 1:
        raise RuntimeError(f"{label}: expected one replacement, got {count}")
    return updated


def main() -> None:
    source = TARGET.read_text(encoding="utf-8")

    if "maxPriorCloseAgeDays" not in source:
        source = replace_once(
            source,
            r"priceSourceId: 'CLOSE_PRICE_SHEET'\n};",
            "priceSourceId: 'CLOSE_PRICE_SHEET',\n  maxPriorCloseAgeDays: 4\n};",
            "config",
        )

    source = replace_once(
        source,
        r"""    for \(var rowIndex = values\.length - 1; rowIndex >= 1; rowIndex -= 1\) \{
      var row = values\[rowIndex\] \|\| \[\];
      var date = dashboardNormalizeDateKey_\(row\[index\['日付'\]\]\);
      if \(!date\) continue;

      var metricRow = dashboardBuildPriceMetricRow_\(date, row, index\);
      if \(!Object\.keys\(metricRow\.markets\)\.length\) continue;
      if \(!source\.byDate\[date\]\) source\.byDate\[date\] = metricRow;
      if \(!source\.latest\) source\.latest = metricRow;
    \}""",
        """    for (var rowIndex = values.length - 1; rowIndex >= 1; rowIndex -= 1) {
      var row = values[rowIndex] || [];
      var date = dashboardNormalizeDateKey_(row[index['日付']]);
      if (!date) continue;

      var metricRow = dashboardBuildPriceMetricRow_(date, row, index);
      if (!Object.keys(metricRow.markets).length) continue;

      // 同一日付が複数ある場合は、シート下側の行を優先する。
      if (!source.byDate[date]) source.byDate[date] = metricRow;

      // 行位置ではなく、正規化済みの日付そのものを比較して最新を決める。
      // 過去データがシート末尾へ混入しても latest には採用しない。
      if (!source.latest || date > source.latest.date) {
        source.latest = source.byDate[date];
      }
    }""",
        "latest row selection",
    )

    source = replace_once(
        source,
        r"""function dashboardNormalizeDateKey_\(value\) \{
  var text = String\(value \|\| ''\)\.trim\(\);
  if \(!text\) return '';

  var match = text\.match\(/\(\\d\{4\}\)\[\\/\.\\-年\]\(\\d\{1,2\}\)\[\\/\.\\-月\]\(\\d\{1,2\}\)/\);
  if \(!match\) return '';

  var year = match\[1\];
  var month = \('0' \+ match\[2\]\)\.slice\(-2\);
  var day = \('0' \+ match\[3\]\)\.slice\(-2\);
  return year \+ '-' \+ month \+ '-' \+ day;
\}""",
        """function dashboardNormalizeDateKey_(value) {
  var text = String(value || '').trim();
  if (!text) return '';

  var match = text.match(/(\\d{4})[\\/.\\-年](\\d{1,2})[\\/.\\-月](\\d{1,2})/);
  if (!match) return '';

  var yearNumber = Number(match[1]);
  var monthNumber = Number(match[2]);
  var dayNumber = Number(match[3]);
  if (yearNumber < 2000 || yearNumber > 2100) return '';
  if (monthNumber < 1 || monthNumber > 12) return '';
  if (dayNumber < 1 || dayNumber > 31) return '';

  var checked = new Date(Date.UTC(yearNumber, monthNumber - 1, dayNumber));
  if (
    checked.getUTCFullYear() !== yearNumber ||
    checked.getUTCMonth() !== monthNumber - 1 ||
    checked.getUTCDate() !== dayNumber
  ) return '';

  var month = ('0' + monthNumber).slice(-2);
  var day = ('0' + dayNumber).slice(-2);
  return yearNumber + '-' + month + '-' + day;
}""",
        "date validation",
        flags=re.S,
    )

    source = source.replace(
        "var changePair = dashboardFormatSignedPair_(change, pct);",
        "var changePair = dashboardFormatSignedPair_(change, pct, close);",
        1,
    )

    source = replace_once(
        source,
        r"""function dashboardApplyPriceSheetMetrics_\(prepared, priceSource, useLatestPriceFallback\) \{[\s\S]*?\n\}\n\nfunction dashboardFormatSignedPair_""",
        """function dashboardApplyPriceSheetMetrics_(prepared, priceSource, useLatestPriceFallback) {
  if (!priceSource || priceSource.status !== 'ok') return;

  var exactRow = priceSource.byDate[prepared.date];
  var priceRow = exactRow || null;
  var matchType = exactRow ? 'date' : '';

  // 07:00（および土曜09:00）の朝レポートだけ、直近営業日の終値を許可する。
  // 12:00・16:00・21:00は本文の当日価格を優先し、前営業日終値では上書きしない。
  if (
    !priceRow &&
    useLatestPriceFallback &&
    dashboardCanUsePriorCloseFallback_(prepared, priceSource.latest)
  ) {
    priceRow = priceSource.latest;
    matchType = 'prior_close';
  }

  if (!priceRow || !priceRow.markets) return;

  var markets = dashboardMarketsByName_(prepared.markets);
  dashboardMarketDefinitions_().forEach(function(definition) {
    var market = markets[definition.name];
    var metric = priceRow.markets[definition.name];
    if (!market || !metric || !metric.price) return;

    market.price = metric.price;
    market.change = metric.change || market.change;
    market.priceSource = {
      id: DASHBOARD_JSON_CONFIG.priceSourceId,
      sheetName: priceSource.sheetName,
      asOf: priceRow.date,
      match: matchType
    };
  });

  prepared.marketDataAsOf = priceRow.date;
  prepared.marketDataSource = priceSource.sheetName;
}

function dashboardCanUsePriorCloseFallback_(prepared, priceRow) {
  if (!prepared || !priceRow || !priceRow.date) return false;
  var reportTime = String(prepared.time || '');
  if (reportTime !== '07:00' && reportTime !== '09:00') return false;

  var gapDays = dashboardDateDistanceDays_(prepared.date, priceRow.date);
  return gapDays >= 1 && gapDays <= DASHBOARD_JSON_CONFIG.maxPriorCloseAgeDays;
}

function dashboardDateDistanceDays_(laterDate, earlierDate) {
  if (!/^\\d{4}-\\d{2}-\\d{2}$/.test(String(laterDate || ''))) return NaN;
  if (!/^\\d{4}-\\d{2}-\\d{2}$/.test(String(earlierDate || ''))) return NaN;

  var later = new Date(String(laterDate) + 'T00:00:00+09:00');
  var earlier = new Date(String(earlierDate) + 'T00:00:00+09:00');
  if (isNaN(later.getTime()) || isNaN(earlier.getTime())) return NaN;
  return Math.round((later.getTime() - earlier.getTime()) / 86400000);
}

function dashboardFormatSignedPair_""",
        "price application",
        flags=re.S,
    )

    source = replace_once(
        source,
        r"""function dashboardFormatSignedPair_\(change, pct\) \{[\s\S]*?\n\}\n\nfunction dashboardNormalizePercentText_\(value\) \{[\s\S]*?\n\}""",
        """function dashboardFormatSignedPair_(change, pct, close) {
  var values = [];
  var cleanChange = dashboardCleanSheetValue_(change);
  var cleanPct = dashboardNormalizePercentText_(pct, close, change);
  if (cleanChange) values.push(cleanChange);
  if (cleanPct) values.push(cleanPct);
  return values.join('、');
}

function dashboardNormalizePercentText_(value, close, change) {
  var providedText = dashboardCleanSheetValue_(value);
  var closeNumber = dashboardParseSheetNumber_(close);
  var changeNumber = dashboardParseSheetNumber_(change);
  var normalizedNumber = NaN;

  // 終値と前日比が取得できる場合は、騰落率を必ず再計算する。
  // セルの表示形式が100倍になっていても、その値をそのまま採用しない。
  if (isFinite(closeNumber) && isFinite(changeNumber)) {
    var previousClose = closeNumber - changeNumber;
    if (previousClose !== 0) {
      normalizedNumber = changeNumber / previousClose * 100;
    }
  }

  if (!isFinite(normalizedNumber) && providedText) {
    normalizedNumber = dashboardParseSheetNumber_(providedText);
  }

  if (!isFinite(normalizedNumber)) return '';
  if (Math.abs(normalizedNumber) > 1000) return '';
  return dashboardFormatPercentNumber_(normalizedNumber);
}

function dashboardParseSheetNumber_(value) {
  var text = dashboardNormalizeInlineText_(value);
  if (!text) return NaN;

  var isNegativeTriangle = /^▲/.test(text);
  text = text
    .replace(/[，,\\s]/g, '')
    .replace(/[−–—]/g, '-')
    .replace(/[^0-9.+-]/g, '');
  if (!text || text === '+' || text === '-' || text === '.') return NaN;

  var number = Number(text);
  if (!isFinite(number)) return NaN;
  return isNegativeTriangle ? -Math.abs(number) : number;
}

function dashboardFormatPercentNumber_(value) {
  var rounded = Math.round(value * 100) / 100;
  var sign = rounded > 0 ? '+' : '';
  return sign + rounded.toFixed(2) + '％';
}""",
        "percent validation",
        flags=re.S,
    )

    marker = "// Root-fix version: 2026-08-06 13:22 JST\n"
    if not source.startswith(marker):
        source = marker + source

    TARGET.write_text(source, encoding="utf-8")
    print(f"Patched {TARGET}")


if __name__ == "__main__":
    main()
