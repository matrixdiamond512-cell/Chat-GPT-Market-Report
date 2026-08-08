#!/usr/bin/env python3
"""Build a verified 52-week foreign-investor flow and Nikkei futures-price series.

TSE Prime cash flow and Nikkei 225 futures flow are compared only when they use
the same weekly period end. Missing weeks are never estimated.

JPX weekly derivatives changed format in April 2026, so current CSV and legacy
PDF files are parsed separately. Legacy cash PDFs are also read structurally:
the current-week Trading Value is the numeric token immediately before the
second ratio in each Sales/Purchases row, making the parser independent of
whether a Balance cell is printed.
"""
from __future__ import annotations

import csv
import io
import json
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from pypdf import PdfReader

import update_nikkei225_supply_demand as u

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'data/nikkei225-supply-demand.json'
HISTORY_WEEKS = 52

CASH_ARCHIVES = [
    'https://www.jpx.co.jp/markets/statistics-equities/investor-type/00-00-archives-00.html',
    'https://www.jpx.co.jp/markets/statistics-equities/investor-type/00-00-archives-01.html',
]
SECTOR_ARCHIVES = [
    'https://www.jpx.co.jp/markets/statistics-derivatives/sector/00-archives-00.html',
    'https://www.jpx.co.jp/markets/statistics-derivatives/sector/00-archives-01.html',
]
KABUTAN_FUTURES_HISTORY = 'https://s.kabutan.jp/futures/%E6%97%A5%E7%B5%8C225%E5%85%88%E7%89%A9/historical_prices/daily/'


def _value_before_second_ratio(line: str) -> float | None:
    """Get the current-period Trading Value from a two-period JPX row."""
    tokens = re.findall(r'▲?[+-]?[\d,]+(?:\.\d+)?', line)
    ratio_indexes = [i for i, tok in enumerate(tokens) if '.' in tok.replace(',', '')]
    if len(ratio_indexes) < 2 or ratio_indexes[1] < 1:
        return None
    return u.n(tokens[ratio_indexes[1] - 1].replace('▲', ''))


def cash_pdf(url: str) -> dict[str, Any] | None:
    """Parse TSE Prime Foreigners current-week cash Trading Value from page 1."""
    raw = u.get(url).content
    reader = PdfReader(io.BytesIO(raw))
    if not reader.pages:
        return None
    text = reader.pages[0].extract_text() or ''
    if not re.search(r'(?:東証プライム|TSE\s*Prime)', text, re.I):
        return None
    if not re.search(r'(?:海外投資家|Foreigners)', text, re.I):
        return None

    dm = re.search(
        r'(20\d{2})年\s*\d{1,2}月.*?\(\s*(\d{1,2})/(\d{1,2})\s*[-〜～]\s*(\d{1,2})/(\d{1,2})\s*\)',
        text,
        re.S,
    )
    if not dm:
        return None
    y, end_m, end_d = int(dm.group(1)), int(dm.group(4)), int(dm.group(5))

    lines = [re.sub(r'\s+', ' ', x).strip() for x in text.splitlines()]
    sales_line = next((x for x in lines if re.search(r'海外投資家(?:計)?', x) and re.search(r'売り\s*Sales', x, re.I)), None)
    buy_line = next((x for x in lines if re.search(r'Foreigners?', x, re.I) and re.search(r'買い\s*Purchases', x, re.I)), None)
    if sales_line is None or buy_line is None:
        return None

    sales = _value_before_second_ratio(sales_line)
    purchases = _value_before_second_ratio(buy_line)
    if sales is None or purchases is None:
        return None
    # TSE Prime Trading Value PDF unit is 1,000 yen.
    return {
        'cashNet': (purchases - sales) / 100_000,
        'asOfDate': date(y, end_m, end_d).isoformat(),
        'cashSourceFileUrl': url,
    }


def derivative_new_csv(url: str) -> dict[str, Any] | None:
    text = u.decode(u.get(url).content)
    rows = list(csv.reader(io.StringIO(text)))
    for r in rows[1:]:
        if len(r) < 12:
            continue
        if r[0].strip() == '301' and r[5].strip() == '60' and r[6].strip() == '2':
            sell = u.n(r[7])
            buy = u.n(r[9])
            if sell is None or buy is None:
                continue
            try:
                asof = datetime.strptime(r[4].strip(), '%Y%m%d').date().isoformat()
            except Exception:
                asof = None
            return {
                'nikkeiFuturesNet': (buy - sell) / 100_000_000,
                'asOfDate': asof,
                'derivativesSourceFileUrl': url,
                'derivativesSourceFormat': 'JPX CSV current format',
            }
    return None


def derivative_old_pdf(url: str) -> dict[str, Any] | None:
    raw = u.get(url).content
    reader = PdfReader(io.BytesIO(raw))
    if not reader.pages:
        return None
    # In the legacy PDF the large Nikkei 225 Futures table is page 1. pypdf
    # extracts its numeric rows before the title, so use the entire page.
    text = reader.pages[0].extract_text() or ''
    if not re.search(r'Nikkei\s*225\s*Futures', text, re.I):
        return None
    if not re.search(r'(?:海外投資家計|Foreigners)', text, re.I):
        return None
    if not re.search(r'(?:単位\s*,?\s*千円|units?,?\s*1,?000\s*yen)', text, re.I):
        return None

    dm = re.search(
        r'(20\d{2})年\s*(\d{1,2})月.*?\(\s*(\d{1,2})/(\d{1,2})\s*[-〜～]\s*(\d{1,2})/(\d{1,2})\s*\)',
        text,
        re.S,
    )
    if dm:
        y, end_m, end_d = int(dm.group(1)), int(dm.group(5)), int(dm.group(6))
    else:
        fm = re.search(r'Tousi_DV_W_(20\d{2})(\d{2})_\d+_\d{4}_(\d{2})(\d{2})', url, re.I)
        if not fm:
            return None
        y, end_m, end_d = int(fm.group(1)), int(fm.group(3)), int(fm.group(4))

    lines = [re.sub(r'\s+', ' ', x).strip() for x in text.splitlines()]
    sales = [x for x in lines if re.match(r'^(?:売り\s+Sales|Sales\b)', x, re.I)]
    purchases = [x for x in lines if re.match(r'^(?:買い\s+Purchases|Purchases\b)', x, re.I)]
    # Overall rows = indexes 0-2; Brokerage breakdown: Institutions=3,
    # Individuals=4, Foreigners=5, Securities Cos.=6.
    if len(sales) < 6 or len(purchases) < 6:
        return None
    sell_value = _value_before_second_ratio(sales[5])
    buy_value = _value_before_second_ratio(purchases[5])
    if sell_value is None or buy_value is None:
        return None
    return {
        'nikkeiFuturesNet': (buy_value - sell_value) / 100_000,
        'asOfDate': date(y, end_m, end_d).isoformat(),
        'derivativesSourceFileUrl': url,
        'derivativesSourceFormat': 'JPX PDF legacy format',
    }


def direction(cash: float | None, fut: float | None) -> str:
    if cash is None or fut is None:
        return '判定待ち'
    if cash > 0 and fut > 0:
        return '現物・先物とも買い'
    if cash < 0 and fut < 0:
        return '現物・先物とも売り'
    if cash < 0 and fut > 0:
        return '現物売り・先物買い'
    if cash > 0 and fut < 0:
        return '現物買い・先物売り'
    return '方向混在'


def valid_old_series(prev: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in prev.get('series') or []:
        if not isinstance(row, dict):
            continue
        dt, cash, fut = row.get('asOfDate'), row.get('cashNet'), row.get('nikkeiFuturesNet')
        if not dt or cash is None or fut is None:
            continue
        out[str(dt)[:10]] = {
            'asOfDate': str(dt)[:10],
            'cashNet': cash,
            'nikkeiFuturesNet': fut,
            'nikkeiFuturesPrice': row.get('nikkeiFuturesPrice'),
            'direction': row.get('direction') or direction(cash, fut),
            'cashSourceFileUrl': row.get('cashSourceFileUrl'),
            'derivativesSourceFileUrl': row.get('derivativesSourceFileUrl'),
            'derivativesSourceFormat': row.get('derivativesSourceFormat'),
            'futuresPriceSourceUrl': row.get('futuresPriceSourceUrl'),
        }
    return out


def all_links(pages: list[str], pattern: str, limit: int = 80) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for page in pages:
        try:
            soup = BeautifulSoup(u.get(page).text, 'html.parser')
            for a in soup.find_all('a', href=True):
                url = urljoin(page, a['href'])
                if re.search(pattern, url, re.I) and url not in seen:
                    seen.add(url)
                    out.append(url)
                    if len(out) >= limit:
                        return out
        except Exception:
            pass
    return out


def kabutan_futures_prices(target_dates: list[str]) -> dict[str, float]:
    wanted = {str(x)[:10] for x in target_dates}
    by_md = {(int(x[5:7]), int(x[8:10])): x for x in wanted}
    found: dict[str, float] = {}
    # Pages are newest first. Month/day repeats in older years, so the first
    # match is the correct year for this latest-52-week window and must never
    # be overwritten by the same month/day from the previous year.
    for page in range(1, 25):
        url = KABUTAN_FUTURES_HISTORY if page == 1 else f'{KABUTAN_FUTURES_HISTORY}?page={page}'
        soup = BeautifulSoup(u.get(url).text, 'html.parser')
        for tr in soup.find_all('tr'):
            cells = [c.get_text(' ', strip=True) for c in tr.find_all(['th', 'td'])]
            if len(cells) < 5:
                continue
            m = re.search(r'(\d{1,2})月\s*(\d{1,2})日', cells[0])
            if not m:
                continue
            target = by_md.get((int(m.group(1)), int(m.group(2))))
            if not target or target in found:
                continue
            close = u.n(cells[4])
            if close is not None:
                found[target] = float(close)
        if len(found) >= len(wanted):
            break
    return found


def main() -> None:
    d = json.loads(OUT.read_text(encoding='utf-8'))
    prev = d.get('foreignInvestors') or {}
    base = {
        'sourceName': 'JPX 投資部門別売買状況',
        'sourceUrl': u.URLS['sector'],
        'cashNote': '東証プライム現物の海外投資家売買（金額ベース）',
        'nikkeiNote': '日経225先物の海外投資家売買（金額ベース）',
        'topixNote': 'TOPIX先物は商品コード検証後に追加',
        'comment': '週次の現物と日経225先物を同一期間で比較。日次の売買主体とは断定しません。',
        'futuresPriceSourceName': '株探 日経225先物時系列（取引所発表の清算値・帳入値）',
        'futuresPriceSourceUrl': KABUTAN_FUTURES_HISTORY,
        'futuresPriceDefinition': '各週の基準日と同日の取引所発表清算値（帳入値）。実際の最終約定価格とは異なる場合があります。',
    }
    debug: dict[str, Any] = {}
    try:
        cashlinks = all_links([u.URLS['cash'], *CASH_ARCHIVES], r'stock_val_1_\d+\.pdf(?:\?|$)', 80)
        cr: list[dict[str, Any]] = []
        cash_failures: list[str] = []
        for url in cashlinks:
            try:
                x = cash_pdf(url)
                if x:
                    cr.append(x)
                else:
                    cash_failures.append(url.rsplit('/',1)[-1])
            except Exception:
                cash_failures.append(url.rsplit('/',1)[-1])
        cr.sort(key=lambda x: x['asOfDate'], reverse=True)

        sector_pages = [u.URLS['sector'], *SECTOR_ARCHIVES]
        new_links = all_links(sector_pages, r'Tousi_DV_W_20\d{6}_20\d{6}\.csv(?:\?|$)', 40)
        old_links = all_links(sector_pages, r'Tousi_DV_W_20\d{4}_\d+_\d{4}_\d{4}\.pdf(?:\?|$)', 80)
        dr: list[dict[str, Any]] = []
        for url in new_links:
            try:
                x = derivative_new_csv(url)
                if x:
                    dr.append(x)
            except Exception:
                pass
        for url in old_links:
            try:
                x = derivative_old_pdf(url)
                if x:
                    dr.append(x)
            except Exception:
                pass
        dr.sort(key=lambda x: x.get('asOfDate') or '', reverse=True)

        by_cash = {x['asOfDate']: x for x in cr if x.get('asOfDate')}
        by_deriv = {x['asOfDate']: x for x in dr if x.get('asOfDate')}
        target_cash_dates = sorted(by_cash)[-HISTORY_WEEKS:]
        missing_deriv = [x for x in target_cash_dates if x not in by_deriv]
        matched = sorted(set(by_cash) & set(by_deriv))
        debug = {
            'cashLinkCount': len(cashlinks),
            'cashParsedWeeks': len(by_cash),
            'cashFailureCount': len(cash_failures),
            'cashFailureFiles': cash_failures[:12],
            'derivativesParsedWeeks': len(by_deriv),
            'matchedWeeks': len(matched),
            'missingDerivativeDatesWithinLatest52CashWeeks': missing_deriv,
        }
        if len(matched) < HISTORY_WEEKS:
            raise ValueError(f'52-week history incomplete: {len(matched)}/52; cash={len(by_cash)}, deriv={len(by_deriv)}, missingDeriv={missing_deriv}')

        merged = valid_old_series(prev)
        for dt in matched:
            c, f = by_cash[dt], by_deriv[dt]
            old = merged.get(dt) or {}
            merged[dt] = {
                'asOfDate': dt,
                'cashNet': c['cashNet'],
                'nikkeiFuturesNet': f['nikkeiFuturesNet'],
                'nikkeiFuturesPrice': old.get('nikkeiFuturesPrice'),
                'direction': direction(c['cashNet'], f['nikkeiFuturesNet']),
                'cashSourceFileUrl': c['cashSourceFileUrl'],
                'derivativesSourceFileUrl': f['derivativesSourceFileUrl'],
                'derivativesSourceFormat': f.get('derivativesSourceFormat'),
                'futuresPriceSourceUrl': old.get('futuresPriceSourceUrl'),
            }
        series = [merged[k] for k in sorted(merged)][-HISTORY_WEEKS:]
        if len(series) != HISTORY_WEEKS:
            raise ValueError(f'52-week merged series incomplete: {len(series)}/52')

        prices = kabutan_futures_prices([x['asOfDate'] for x in series])
        for row in series:
            px = prices.get(row['asOfDate'])
            if px is not None:
                row['nikkeiFuturesPrice'] = px
                row['futuresPriceSourceUrl'] = KABUTAN_FUTURES_HISTORY
        missing_prices = [x['asOfDate'] for x in series if x.get('nikkeiFuturesPrice') is None]
        debug['missingPriceDates'] = missing_prices
        if missing_prices:
            raise ValueError('52-week futures price history incomplete: ' + ','.join(missing_prices))

        latest = series[-1]
        current_weeks = sum(x.get('derivativesSourceFormat') == 'JPX CSV current format' for x in series)
        legacy_weeks = sum(x.get('derivativesSourceFormat') == 'JPX PDF legacy format' for x in series)
        d['foreignInvestors'] = {
            **base,
            'cashNet': latest['cashNet'],
            'nikkeiFuturesNet': latest['nikkeiFuturesNet'],
            'nikkeiFuturesPrice': latest['nikkeiFuturesPrice'],
            'topixFuturesNet': None,
            'asOfDate': latest['asOfDate'],
            'cashSourceFileUrl': latest['cashSourceFileUrl'],
            'derivativesSourceFileUrl': latest['derivativesSourceFileUrl'],
            'direction': latest['direction'],
            'series': series,
            'historyWeeks': 52,
            'historyTargetWeeks': 52,
            'historyStatus': 'verified',
            'priceHistoryWeeks': 52,
            'priceHistoryStatus': 'verified',
            'derivativesCurrentFormatWeeks': current_weeks,
            'derivativesLegacyFormatWeeks': legacy_weeks,
            'historyPolicy': '52-weeks-current-plus-official-archives-same-week-only-no-fabrication',
            'archiveSources': {'cash': CASH_ARCHIVES, 'derivatives': SECTOR_ARCHIVES},
            'status': 'verified',
            'fetchedAt': u.now(),
        }
    except Exception as exc:
        d['foreignInvestors'] = u.stale(prev, base, f'JPX海外投資家取得失敗: {type(exc).__name__}: {exc}')

    d['assessment'] = u.assessment(d.get('futures') or {}, d.get('arbitrage') or {}, d.get('options') or {}, d.get('foreignInvestors') or {})
    keys = ('spot','futures','sessions','arbitrage','options','participantFlow','foreignInvestors','participantOpenInterest','shortSelling','margin')
    statuses = {k: (d.get(k) or {}).get('status','unavailable') for k in keys}
    d['sourceStatus'] = f"{sum(v in {'verified','calculated'} for v in statuses.values())}/10項目連携（基準日を個別表示）"
    d.setdefault('diagnostics', {})['statuses'] = statuses
    d['diagnostics']['foreignParser'] = 'JPX Prime page-1 cash + Nikkei 225 futures exact 52 matched weeks; current CSV + legacy official PDF; Kabutan settlement prices on same dates'
    d['diagnostics']['foreign52Debug'] = debug
    d['generatedAt'] = u.now()
    OUT.write_text(json.dumps(d, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(d['foreignInvestors'], ensure_ascii=False))


if __name__ == '__main__':
    main()
