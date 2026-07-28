(() => {
  const byId = id => document.getElementById(id);
  const usSectorsEl = byId('dashboardUsSectors');
  const jpSectorsEl = byId('dashboardJapanSectors');
  const nikkeiEl = byId('dashboardNikkeiContributors');
  const usMoversEl = byId('dashboardUsMovers');
  const conclusionEl = byId('dashboardConclusion');
  const riskEl = byId('dashboardRisk');
  const latestEl = byId('latestReport');
  if (!usSectorsEl || !jpSectorsEl || !nikkeiEl || !usMoversEl) return;

  const arr = value => Array.isArray(value) ? value : (value ? [value] : []);
  const textOf = item => typeof item === 'string' ? item : (item?.text || item?.summary || item?.title || item?.name || '');
  const clean = value => String(value || '').replace(/^\s*[・●■◆◇▶▷▲△▼▽―—-]\s*/, '').replace(/\s+/g, ' ').trim();
  const escapeHtml = value => String(value || '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[c]));

  const direction = value => {
    const t = String(value || '').toLowerCase();
    if (/上昇|値上がり|プラス|買われ|買い優勢|堅調|反発|押し上げ|up|gain|positive/.test(t)) return 'up';
    if (/下落|値下がり|マイナス|売られ|売り優勢|軟調|反落|押し下げ|down|loss|negative/.test(t)) return 'down';
    return 'neutral';
  };

  function getCurrentReport() {
    const source = typeof reports !== 'undefined' && Array.isArray(reports) ? reports : [];
    if (!source.length) return null;
    if (typeof selectedKey !== 'undefined' && selectedKey) {
      const found = source.find(r => `${r.date} ${r.time}` === selectedKey);
      if (found) return found;
    }
    return source[0];
  }

  function splitStringRow(value) {
    let text = clean(value);
    let valueText = '';

    const valueMatch = text.match(/(?:^|\s)([+＋-−▲▼]?\d+(?:\.\d+)?(?:%|％|円|ドル|ポイント|pt|bp))(?=\s|$|[、。｜|])/i);
    if (valueMatch) {
      valueText = valueMatch[1];
      text = clean(text.replace(valueMatch[0], ' '));
    }

    const reasonPatterns = [
      /^(.*?)\s*[：:]\s*(.+)$/,
      /^(.*?)\s*[｜|]\s*(.+)$/,
      /^(.*?)\s*[→⇒]\s*(.+)$/,
      /^(.*?)\s*[―—]\s*(.+)$/
    ];
    for (const pattern of reasonPatterns) {
      const match = text.match(pattern);
      if (match && clean(match[1]).length <= 80) {
        return {
          name: clean(match[1]).replace(/^(買われた|売られた|上昇|下落|プラス寄与|マイナス寄与)(?:セクター|業種|銘柄)?\s*/,'') || clean(match[1]),
          note: clean(match[2]).replace(/^(理由|背景|要因)\s*[：:]?\s*/,'') ,
          value: valueText,
          direction: direction(text)
        };
      }
    }

    return { name: text, note: '', value: valueText, direction: direction(text) };
  }

  function normalizeRows(value, forcedDirection = '') {
    return arr(value).map(item => {
      if (typeof item === 'string') {
        const row = splitStringRow(item);
        if (forcedDirection) row.direction = forcedDirection;
        return row;
      }
      const name = clean(item?.name || item?.title || item?.sector || item?.industry || item?.ticker || item?.symbol || item?.stock);
      const note = clean(
        item?.reason || item?.boughtReason || item?.soldReason || item?.riseReason || item?.fallReason ||
        item?.driver || item?.catalyst || item?.note || item?.material || item?.summary || item?.description
      );
      return {
        name,
        note,
        value: clean(item?.change || item?.rate || item?.contribution || item?.value || item?.percent),
        direction: forcedDirection || clean(item?.direction || direction(`${name} ${note}`))
      };
    }).filter(row => row.name);
  }

  function extractLines(report, includePatterns, excludePatterns = []) {
    const raw = [report?.fullText, ...arr(report?.sectors).map(textOf), ...arr(report?.news).map(textOf)].filter(Boolean).join('\n');
    return raw.split(/\n+/).map(clean).filter(line => line.length >= 4 && includePatterns.some(p => p.test(line)) && !excludePatterns.some(p => p.test(line)));
  }

  function uniqueRows(rows, limit = 8) {
    const seen = new Set();
    return rows.filter(row => {
      const key = `${clean(row.name)}|${clean(row.note)}`.toLowerCase();
      if (!key || seen.has(key)) return false;
      seen.add(key);
      return true;
    }).slice(0, limit);
  }

  function rowsFromKeys(report, keys, forcedDirection = '') {
    for (const key of keys) {
      const rows = normalizeRows(report?.[key], forcedDirection);
      if (rows.length) return rows;
    }
    return [];
  }

  function sectorRows(report, market) {
    const keys = market === 'us'
      ? ['usSectors','usSectorPerformance','usIndustries','americanSectors']
      : ['japanSectors','tokyoSectors','japanIndustries','tseSectors'];
    for (const key of keys) {
      const rows = normalizeRows(report?.[key]);
      if (rows.length) return uniqueRows(rows, 12);
    }
    const found = extractLines(report,
      market === 'us'
        ? [/米国.*(?:セクター|業種)/, /S&P.?500.*(?:セクター|業種)/i, /SOX|NASDAQ100|ラッセル2000|Russell 2000/i, /米株.*(?:買われ|売られ)/]
        : [/東京市場.*(?:セクター|業種)/, /東証.*(?:業種|セクター)/, /日本株.*(?:買われ|売られ)/, /銀行|商社|海運|自動車|電機|半導体|医薬品|小売|不動産/],
      market === 'us' ? [/東京|東証|日経/] : [/米国|S&P|NASDAQ|SOX|Russell/i]
    );
    return uniqueRows(normalizeRows(found),12);
  }

  function sectorGroups(report, market) {
    const boughtKeys = market === 'us'
      ? ['usBoughtSectors','usSectorGainers','usBoughtIndustries','usBoughtReasons']
      : ['japanBoughtSectors','tokyoBoughtSectors','japanSectorGainers','japanBoughtReasons'];
    const soldKeys = market === 'us'
      ? ['usSoldSectors','usSectorLosers','usSoldIndustries','usSoldReasons']
      : ['japanSoldSectors','tokyoSoldSectors','japanSectorLosers','japanSoldReasons'];

    const explicitBought = rowsFromKeys(report,boughtKeys,'up');
    const explicitSold = rowsFromKeys(report,soldKeys,'down');
    const base = sectorRows(report,market);
    const bought = explicitBought.length ? explicitBought : base.filter(row => direction(`${row.direction} ${row.name} ${row.note}`) === 'up');
    const sold = explicitSold.length ? explicitSold : base.filter(row => direction(`${row.direction} ${row.name} ${row.note}`) === 'down');
    const neutral = base.filter(row => direction(`${row.direction} ${row.name} ${row.note}`) === 'neutral');
    return {bought:uniqueRows(bought,8),sold:uniqueRows(sold,8),neutral:uniqueRows(neutral,5)};
  }

  function contributorRows(report, positive) {
    const keys = positive
      ? ['nikkeiPositiveContributors','nikkeiPlusContributors','positiveContributors','nikkeiContributorsUp']
      : ['nikkeiNegativeContributors','nikkeiMinusContributors','negativeContributors','nikkeiContributorsDown'];
    for (const key of keys) {
      const rows = normalizeRows(report?.[key],positive?'up':'down');
      if (rows.length) return uniqueRows(rows,8);
    }
    const found = extractLines(report, positive
      ? [/寄与度.*(?:プラス|上位)/, /プラス寄与/, /押し上げ寄与/, /日経.*押し上げ/]
      : [/寄与度.*(?:マイナス|下位)/, /マイナス寄与/, /押し下げ寄与/, /日経.*押し下げ/]);
    return uniqueRows(normalizeRows(found,positive?'up':'down'),8);
  }

  function moverRows(report, gainers) {
    const keys = gainers
      ? ['usGainers','usTopGainers','usStockGainers','americanGainers']
      : ['usLosers','usTopLosers','usStockLosers','americanLosers'];
    for (const key of keys) {
      const rows = normalizeRows(report?.[key],gainers?'up':'down');
      if (rows.length) return uniqueRows(rows,8);
    }
    const found = extractLines(report, gainers
      ? [/米国.*(?:大幅上昇|値上がり|上昇率上位)/, /S&P.*上昇率上位/i, /NASDAQ.*上昇率上位/i]
      : [/米国.*(?:大幅下落|値下がり|下落率上位)/, /S&P.*下落率上位/i, /NASDAQ.*下落率上位/i]);
    return uniqueRows(normalizeRows(found,gainers?'up':'down'),8);
  }

  function reasonLabel(row, label) {
    if (!row.note) return `<small><b>${escapeHtml(label)}：</b>理由の記載なし</small>`;
    return `<small><b>${escapeHtml(label)}：</b>${escapeHtml(row.note)}</small>`;
  }

  function renderRows(rows, emptyText, reasonText = '理由') {
    if (!rows.length) return `<p class="market-depth-empty">${escapeHtml(emptyText)}</p><span class="source-status is-missing">原文に該当データなし</span>`;
    return `<div class="market-depth-list">${rows.map((row,i) => `<div class="market-depth-row">
      <span class="market-depth-rank">${i+1}</span>
      <span class="market-depth-main"><strong>${escapeHtml(row.name)}</strong>${reasonLabel(row,reasonText)}</span>
      ${row.value?`<span class="market-depth-value ${direction(row.direction||row.value||row.name)}">${escapeHtml(row.value)}</span>`:''}
    </div>`).join('')}</div><span class="source-status is-available">レポート原文から表示</span>`;
  }

  function renderSplit(leftTitle,leftRows,rightTitle,rightRows,leftEmpty,rightEmpty,leftReason='理由',rightReason='理由') {
    return `<div class="market-depth-columns">
      <section class="market-depth-column"><h4>${escapeHtml(leftTitle)}</h4>${renderRows(leftRows,leftEmpty,leftReason)}</section>
      <section class="market-depth-column"><h4>${escapeHtml(rightTitle)}</h4>${renderRows(rightRows,rightEmpty,rightReason)}</section>
    </div>`;
  }

  function renderSectorAnalysis(report,market) {
    const groups=sectorGroups(report,market);
    const main=renderSplit('買われたセクター・業種',groups.bought,'売られたセクター・業種',groups.sold,'買われたセクターの記載なし','売られたセクターの記載なし','買われた理由','売られた理由');
    if(!groups.neutral.length) return main;
    return `${main}<details class="market-depth-details"><summary>方向を特定できない記載を表示</summary>${renderRows(groups.neutral,'','背景・理由')}</details>`;
  }

  function readerRows(rows,emptyText,reasonText='理由') {
    if (!rows.length) return `<p class="report-reader-empty">${escapeHtml(emptyText)}</p>`;
    return `<ul>${rows.map(row=>`<li><strong>${escapeHtml(row.name)}</strong>${row.value?` <span class="market-depth-value ${direction(row.direction||row.value||row.name)}">${escapeHtml(row.value)}</span>`:''}<br><small><b>${escapeHtml(reasonText)}：</b>${escapeHtml(row.note||'理由の記載なし')}</small></li>`).join('')}</ul>`;
  }

  function readerSectorGroups(report,market) {
    const groups=sectorGroups(report,market);
    return `<h4>買われたセクター・業種</h4>${readerRows(groups.bought,'記載なし','買われた理由')}<h4>売られたセクター・業種</h4>${readerRows(groups.sold,'記載なし','売られた理由')}${groups.neutral.length?`<h4>方向未判定</h4>${readerRows(groups.neutral,'','背景・理由')}`:''}`;
  }

  function articleInternals(report) {
    const plus=contributorRows(report,true), minus=contributorRows(report,false);
    const gain=moverRows(report,true), loss=moverRows(report,false);
    return `<section class="report-reader-section report-internals-v2" id="reader-internals">
      <h2>9. セクター・業種・個別銘柄</h2>
      <div class="report-reader-copy">
        <h3>米国市場｜買われた業種・売られた業種</h3>${readerSectorGroups(report,'us')}
        <h3>東京市場｜買われた業種・売られた業種</h3>${readerSectorGroups(report,'jp')}
        <h3>日経225｜プラス寄与度上位</h3>${readerRows(plus,'記載なし','押し上げた理由')}
        <h3>日経225｜マイナス寄与度上位</h3>${readerRows(minus,'記載なし','押し下げた理由')}
        <h3>米国市場｜大幅上昇銘柄</h3>${readerRows(gain,'記載なし','上昇した理由')}
        <h3>米国市場｜大幅下落銘柄</h3>${readerRows(loss,'記載なし','下落した理由')}
      </div>
    </section>`;
  }

  function summaryInternals(report) {
    const us=sectorGroups(report,'us'),jp=sectorGroups(report,'jp');
    return `<section class="report-summary-panel report-summary-panel--wide report-internals-v2">
      <h4>セクター・業種・個別銘柄</h4>
      <div class="report-summary-split">
        <div><h5>米国市場｜買われた業種</h5>${readerRows(us.bought.slice(0,3),'記載なし','買われた理由')}<h5>米国市場｜売られた業種</h5>${readerRows(us.sold.slice(0,3),'記載なし','売られた理由')}<h5>米国個別株</h5>${readerRows([...moverRows(report,true).slice(0,2),...moverRows(report,false).slice(0,2)],'記載なし','値動きの理由')}</div>
        <div><h5>東京市場｜買われた業種</h5>${readerRows(jp.bought.slice(0,3),'記載なし','買われた理由')}<h5>東京市場｜売られた業種</h5>${readerRows(jp.sold.slice(0,3),'記載なし','売られた理由')}<h5>日経225寄与度上位</h5>${readerRows([...contributorRows(report,true).slice(0,2),...contributorRows(report,false).slice(0,2)],'記載なし','寄与した理由')}</div>
      </div>
    </section>`;
  }

  function injectIntoReport(report) {
    if (!latestEl || !report || latestEl.querySelector('.report-internals-v2')) return;
    const reader = latestEl.querySelector('.report-reader');
    if (reader) {
      const markets = reader.querySelector('#reader-markets');
      const node=document.createElement('div'); node.innerHTML=articleInternals(report);
      reader.insertBefore(node.firstElementChild,markets||null);
      const toc=reader.querySelector('.report-reader-toc');
      if(toc&&!toc.querySelector('[href="#reader-internals"]')) toc.insertAdjacentHTML('beforeend','<a href="#reader-internals">セクター・個別株</a>');
      return;
    }
    const summaryGrid=latestEl.querySelector('.report-summary-grid');
    if(summaryGrid) summaryGrid.insertAdjacentHTML('beforeend',summaryInternals(report));
  }

  function render(report) {
    if (!report) return;
    if(conclusionEl) conclusionEl.textContent=clean(report.mainScenario||report.conclusion||report.outlook||'記載なし');
    if(riskEl) riskEl.textContent=clean(report.breakConditions||arr(report.riskManagement).map(textOf)[0]||'記載なし');
    usSectorsEl.innerHTML=renderSectorAnalysis(report,'us');
    jpSectorsEl.innerHTML=renderSectorAnalysis(report,'jp');
    nikkeiEl.innerHTML=renderSplit('プラス寄与度上位',contributorRows(report,true),'マイナス寄与度上位',contributorRows(report,false),'プラス寄与度データなし','マイナス寄与度データなし','押し上げた理由','押し下げた理由');
    usMoversEl.innerHTML=renderSplit('大幅上昇銘柄',moverRows(report,true),'大幅下落銘柄',moverRows(report,false),'米国上昇銘柄データなし','米国下落銘柄データなし','上昇した理由','下落した理由');
    injectIntoReport(report);
  }

  const observer = latestEl ? new MutationObserver(()=>setTimeout(()=>render(getCurrentReport()),0)) : null;
  if(observer) observer.observe(latestEl,{childList:true,subtree:false});

  const timer=setInterval(()=>{const report=getCurrentReport();if(!report)return;clearInterval(timer);render(report);},120);
  setTimeout(()=>clearInterval(timer),12000);
})();
