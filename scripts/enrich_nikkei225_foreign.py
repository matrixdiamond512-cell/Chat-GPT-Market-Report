#!/usr/bin/env python3
"""Build 52 weeks of verified foreign-investor cash/futures flow history.

Rules
-----
* Display target is always the latest 52 matching weekly period ends.
* TSE Prime cash flow and Nikkei 225 futures flow must have the same period end.
* No missing week is estimated or interpolated.
* JPX changed the derivatives weekly format in April 2026. New-format CSV files
  are parsed directly; older weeks are read from the official JPX weekly PDF,
  limiting PDF extraction to the Nikkei pages for speed.
* Nikkei 225 futures settlement prices are attached on exactly the same weekly
  dates using Kabutan's daily history, whose close is described as the
  exchange-published settlement/book value.
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


def cash_pdf(url: str) -> dict[str, Any] | None:
    _, text = u.doc(url)
    hm = re.search(
        r'(20\d{2})年\d{1,2}月第\d+週.*?\(\s*\d{1,2}/\d{1,2}\s*[-〜～]\s*(\d{1,2})/(\d{1,2})\s*\)',
        text,
        re.S,
    )
    if not hm:
        return None
    y, mo, dy = int(hm.group(1)), int(hm.group(2)), int(hm.group(3))
    sm = re.search(
        r'海外投資家\s+売り\s+Sales\s+([\d,]+)\s+[\d.]+(?:\s+[▲+-]?\s*[\d,]+)?\s+([\d,]+)\s+[\d.]+',
        text,
    )
    pm = re.search(
        r'Foreigners\s+買い\s+Purchases\s+([\d,]+)\s+[\d.]+(?:\s+[▲+-]?\s*[\d,]+)?\s+([\d,]+)\s+[\d.]+',
        text,
    )
    if not sm or not pm:
        return None
    current_sales = float(sm.group(2).replace(',', ''))
    current_purchases = float(pm.group(2).replace(',', ''))
    return {
        'cashNet': (current_purchases - current_sales) / 100_000,
        'asOfDate': date(y, mo, dy).isoformat(),
        'cashSourceFileUrl': url,
    }


def derivative_new_csv(url: str) -> dict[str, Any] | None:
    """Parse the post-April-2026 JPX CSV layout."""
    text = u.decode(u.get(url).content)
    rows = list(csv.reader(io.StringIO(text)))
    for r in rows[1:]:
        if len(r) < 12:
            continue
        # Product 301 = Nikkei 225 Futures; investor 60 = Foreigners;
        # 2 = monetary value in the current JPX layout.
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


def _value_before_second_ratio(line: str) -> float | None:
    """Extract Trading Value from an old JPX PDF Sales/Purchases row.

    Old rows are laid out as:
      Volume | Ratio | [Balance] | Value | Ratio | [Balance]
    The balance column is blank on one side, so fixed numeric indexes are unsafe.
    Trading Value is reliably the token immediately before the second ratio.
    """
    tokens = re.findall(r'▲?[+-]?[\d,]+(?:\.\d+)?', line)
    ratio_indexes = [i for i, tok in enumerate(tokens) if '.' in tok.replace(',', '')]
    if len(ratio_indexes) < 2 or ratio_indexes[1] < 1:
        return None
    return u.n(tokens[ratio_indexes[1] - 1].replace('▲', ''))


def derivative_old_pdf(url: str) -> dict[str, Any] | None:
    """Parse a pre-April-2026 JPX weekly PDF.

    Nikkei 225 Futures is the first OSE product in the legacy weekly PDF.  PDF
    text extraction separates category labels from numerical rows, but the
    brokerage-category ordering is fixed: Institutions, Individuals,
    Foreigners, Securities Cos.  Therefore the third triplet after the first
    brokerage breakdown header is the Foreigners row.  We validate that the
    section contains both the Nikkei 225 title and Foreigners label before using
    the values.
    """
    raw = u.get(url).content
    reader = PdfReader(io.BytesIO(raw))
    # The large Nikkei 225 futures table occupies the first two pages in the
    # legacy file. Avoid extracting dozens of unrelated product pages.
    text = '\n'.join((reader.pages[i].extract_text() or '') for i in range(min(2, len(reader.pages))))
    marker = re.search(r'日経\s*２?２５\s*先物\s*/\s*Nikkei\s*225\s*Futures', text, re.I)
    if not marker:
        marker = re.search(r'Nikkei\s*225\s*Futures', text, re.I)
    if not marker:
        return None
    section = text[marker.start():]
    end = re.search(r'Nikkei\s*225\s*mini', section, re.I)
    if end:
        section = section[:end.start()]
    if not re.search(r'(?:海外投資家計|Foreigners)', section, re.I):
        return None

    dm = re.search(
        r'(20\d{2})年\d{1,2}月(?:\s*第\d+週)?.*?\(\s*\d{1,2}/\d{1,2}\s*[-〜～]\s*(\d{1,2})/(\d{1,2})\s*\)',
        section,
        re.S,
    )
    if not dm:
        # Fallback to the legacy filename: Tousi_DV_W_YYYYMM_w_MMDD_MMDD
        fm = re.search(r'Tousi_DV_W_(20\d{2})(\d{2})_\d+_\d{4}_(\d{2})(\d{2})', url, re.I)
        if not fm:
            return None
        y, mo, dy = int(fm.group(1)), int(fm.group(3)), int(fm.group(4))
    else:
        y, mo, dy = int(dm.group(1)), int(dm.group(2)), int(dm.group(3))

    lines = [re.sub(r'\s+', ' ', x).strip() for x in section.splitlines()]
    sales = [x for x in lines if re.match(r'^(?:売り\s+Sales|Sales\b)', x, re.I)]
    purchases = [x for x in lines if re.match(r'^(?:買い\s+Purchases|Purchases\b)', x, re.I)]
    # After Total/Proprietary/Brokerage, the brokerage breakdown begins:
    # Institutions (index 3), Individuals (4), Foreigners (5), Securities (6).
    if len(sales) < 6 or len(purchases) < 6:
        return None
    sell_value = _value_before_second_ratio(sales[5])
    buy_value = _value_before_second_ratio(purchases[5])
    if sell_value is None or buy_value is None:
        return None
    # Legacy PDF unit for Nikkei 225 Futures trading value is 1,000 yen.
    return {
        'nikkeiFuturesNet': (buy_value - sell_value) / 100_000,
        'asOfDate': date(y, mo, dy).isoformat(),
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
        dt = row.get('asOfDate')
        cash = row.get('cashNet')
        fut = row.get('nikkeiFuturesNet')
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


def all_links(pages: list[str], pattern: str, limit: int = 70) -> list[str]:
    """Collect file links without update_nikkei225_supply_demand.links()' 40-link cap."""
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
    """Return settlement prices for exact target dates from Kabutan daily history."""
    wanted = {str(x)[:10] for x in target_dates}
    # The 52-week window is shorter than one calendar year, so month/day pairs
    # are unique inside the requested window.
    by_md = {(int(x[5:7]), int(x[8:10])): x for x in wanted}
    found: dict[str, float] = {}
    # ~260 sessions are needed for 52 weeks. Twenty pages gives sufficient room
    # while stopping immediately when all requested dates have been found.
    for page in range(1, 21):
        url = KABUTAN_FUTURES_HISTORY if page == 1 else f'{KABUTAN_FUTURES_HISTORY}?page={page}'
        html = u.get(url).text
        soup = BeautifulSoup(html, 'html.parser')
        for tr in soup.find_all('tr'):
            cells = [c.get_text(' ', strip=True) for c in tr.find_all(['th', 'td'])]
            if len(cells) < 5:
                continue
            m = re.search(r'(\d{1,2})月\s*(\d{1,2})日', cells[0])
            if not m:
                continue
            target = by_md.get((int(m.group(1)), int(m.group(2))))
            if not target:
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
    try:
        cash_pages = [u.URLS['cash'], *CASH_ARCHIVES]
        cashlinks = all_links(cash_pages, r'stock_val_1_\d+\.pdf(?:\?|$)', 70)
        cr: list[dict[str, Any]] = []
        for url in cashlinks:
            try:
                x = cash_pdf(url)
                if x:
                    cr.append(x)
            except Exception:
                pass
        cr.sort(key=lambda x: x['asOfDate'], reverse=True)

        sector_pages = [u.URLS['sector'], *SECTOR_ARCHIVES]
        new_links = all_links(sector_pages, r'Tousi_DV_W_20\d{6}_20\d{6}\.csv(?:\?|$)', 30)
        old_links = all_links(sector_pages, r'Tousi_DV_W_20\d{4}_\d+_\d{4}_\d{4}\.pdf(?:\?|$)', 60)
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
        if not cr or not dr:
            raise ValueError(f'cash={len(cr)} derivative={len(dr)}')

        by_cash = {x['asOfDate']: x for x in cr if x.get('asOfDate')}
        by_deriv = {x['asOfDate']: x for x in dr if x.get('asOfDate')}
        matched = sorted(set(by_cash) & set(by_deriv))
        if not matched:
            raise ValueError('cash and derivative weekly period ends do not match')

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
        if len(series) < HISTORY_WEEKS:
            raise ValueError(f'52-week history incomplete: {len(series)}/{HISTORY_WEEKS}')

        prices = kabutan_futures_prices([x['asOfDate'] for x in series])
        for row in series:
            px = prices.get(row['asOfDate'])
            if px is not None:
                row['nikkeiFuturesPrice'] = px
                row['futuresPriceSourceUrl'] = KABUTAN_FUTURES_HISTORY
        missing = [x['asOfDate'] for x in series if x.get('nikkeiFuturesPrice') is None]
        if missing:
            raise ValueError('52-week futures price history incomplete: ' + ','.join(missing))

        latest = series[-1]
        legacy_weeks = sum(x.get('derivativesSourceFormat') == 'JPX PDF legacy format' for x in series)
        current_weeks = sum(x.get('derivativesSourceFormat') == 'JPX CSV current format' for x in series)
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
            'historyWeeks': len(series),
            'historyTargetWeeks': HISTORY_WEEKS,
            'historyStatus': 'verified',
            'priceHistoryWeeks': sum(x.get('nikkeiFuturesPrice') is not None for x in series),
            'priceHistoryStatus': 'verified',
            'derivativesCurrentFormatWeeks': current_weeks,
            'derivativesLegacyFormatWeeks': legacy_weeks,
            'historyPolicy': '52-weeks-current-plus-official-archives-same-week-only-no-fabrication',
            'archiveSources': {
                'cash': CASH_ARCHIVES,
                'derivatives': SECTOR_ARCHIVES,
            },
            'status': 'verified',
            'fetchedAt': u.now(),
        }
    except Exception as exc:
        d['foreignInvestors'] = u.stale(prev, base, f'JPX海外投資家取得失敗: {type(exc).__name__}: {exc}')

    d['assessment'] = u.assessment(
        d.get('futures') or {},
        d.get('arbitrage') or {},
        d.get('options') or {},
        d.get('foreignInvestors') or {},
    )
    keys = (
        'spot', 'futures', 'sessions', 'arbitrage', 'options', 'participantFlow',
        'foreignInvestors', 'participantOpenInterest', 'shortSelling', 'margin',
    )
    statuses = {k: (d.get(k) or {}).get('status', 'unavailable') for k in keys}
    d['sourceStatus'] = f"{sum(v in {'verified','calculated'} for v in statuses.values())}/10項目連携（基準日を個別表示）"
    d.setdefault('diagnostics', {})['statuses'] = statuses
    d['diagnostics']['foreignParser'] = (
        'JPX Prime cash + Nikkei 225 futures flows, exact 52 matched weeks; '
        'current CSV + legacy official PDF; Kabutan exchange settlement prices on same dates'
    )
    d['generatedAt'] = u.now()
    OUT.write_text(json.dumps(d, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(d['foreignInvestors'], ensure_ascii=False))


if __name__ == '__main__':
    main()
